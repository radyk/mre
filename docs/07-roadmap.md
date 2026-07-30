# Product Roadmap

**Document 7** · Status: v2.66 · Companions: 01–04 (constitution), 05 (Constraint Catalog, in progress), 06 (Incoming Data Spec)

**v2.67:** **Session 4B.21 — one board, contradictory answers** 2026-07-30 (ruling verbatim in docs/04 2026-07-30; narrative in `docs/closeouts/4B.21.md`). 4B.17's **A5, DISCHARGED**. THE RULING: **a count names the disposition it counts**, and **a predicate asserted over a count must apply to every member of the set counted** — where it does not, the set is SPLIT and each part reported with the predicate that applies. Two clauses added by the census: adjacent counts share a denominator or name their own; where the dispositions do not partition the known set, the surface says so and states no total. Census by MECHANISM: **542 raw aggregation sites → 253 candidates on surface-producing files → 8 defects**, plus a separate UNIVERSAL sweep (38 planner-facing, 15 with a placement-presupposing predicate, 3 defects) because the sharpest specimen — *"Every order finishes on time."* — carries no number for an arithmetic census to see. **THIS IS THE FIFTH INSTANCE OF CATEGORY FUSION IN SIX SESSIONS** (delta card 4B.5, `lateness_set` 4B.13, `CostProof` 4B.18, working-time 4B.20, `inventory` 4B.21) and docs/04 records the common mechanism: **a name written once and never re-read as a claim**. A5 closed by scoping ONE list (`ordered_records`), which fixes chain, cited refs, lit bars and the cockpit footer together. docs/01 gains **§6.10**, the disposition vocabulary — retrievable by nothing before this (`"committed"`: zero passages) — and `synthesis_prompt.md` **v4 → v5** rule 12. Guard: agreement + prose, 10 tests, **two negative controls red on opposite halves**, and **the live run caught a seam the guard could not: it supplies its own document, the ask path does not** (§5a.78). §5a.71-78.

**v2.66:** **Session 4B.20 — working time is not elapsed span** 2026-07-30 (ruling verbatim in docs/04 2026-07-30; narrative in `docs/closeouts/4B.20.md`). 4B.17's **A3, DISCHARGED**; A5 named and LEFT. The FOURTH seam of a class fixed three times, and Item 1 enumerated the class before fixing anything: an AST census by ARITHMETIC, not by name — **408 raw sites → 198 time-quantity bindings → 63 OFFSETS → 135 true durations, of which THREE are wrong and one is latent-wrong.** *"Three and no more"* is the result and it is only credible enumerated. THE RULING: **working time and elapsed span are different quantities and are never interchangeable** — any surface reporting one names WHICH, and (end − start) on a chunked operation is a SPAN. Two clauses added with reasons: **a capacity figure names its denominator** (5821 busy minutes against 1501 of open capacity, 3.9x, with nothing on the surface making it checkable), and **a figure the product derives must be quotable by the surface that derives it**. The truer figure **was already on the row** — `run_min`/`span_min` since 4B.14 — and the toolbox discarded it to recompute the subtraction. `board.js` was RIGHT and right **by a property of the data nothing enforces** (§5a.68); the opener was never affected. **MAKING THE ANSWER TRUER MADE IT UNVERIFIABLE**: a correct claim with four real citations was CUT, because working time lives in no single record (§5a.70). Guard: naming register + value property, 19 tests, premise test, **two negative controls proven red**, and it caught an unclassified field on its first run. Governed artifacts: four `TOOL_MEANINGS`, `synthesis_prompt.md` **v3 → v4** rule 11. §5a.67-70.

**v2.65:** **Session 4B.19 — authored copy that asserts board facts** 2026-07-30 (ruling verbatim in docs/04 2026-07-30; narrative in `docs/closeouts/4B.19.md`). 4B.17's **A1 and A2, both DISCHARGED**; A3 and A5 named and LEFT. Item 1 enumerated the class before fixing anything, per 4B.18's method, and **the class has FIFTEEN members, not the two 4B.17 found by accident** — and the census had to widen its own population, because **the entity slot is NOT the mechanism**: `ROUTE_OFFERS["advice"]` carries no slot and is a member on identical grounds, so **the assertion is the mechanism and the interpolation only makes it vivid**. THE RULING: *an offer label names the question it would answer, never the answer* — a door label is composed before any board read, so a label that asserts is a claim made without evidence by construction, in the product's own voice. Gating each door on a board read was considered and REJECTED with its reason. Fifteen labels rewritten with their usefulness intact; four surfaces enumerated and cleared (`INVITATIONS`, `ROUTE_TAXONOMY.canonical`, the cockpit, `planner_language`). THE SECOND FLOOR: **no truncated list of board entities is presented as complete** — *"The machines here are: "* listed **8 of 15** silently, dropping the machine the asked order was actually on, on the correction path FOR A TYPO. Now nearest-matches + the total, with **pilot density (174 workcenters) the reason for the shape**. Six truncations censused: four already correct, two the defect, three further silent cuts closed. Two guards (12 + 10 tests), each with a premise test and a **negative control proven red out-of-process**. §5a.64-66; the last is Item 4's read-only rider — **nothing reads either of 4B.18's two unverified casualty classes**.

**v2.64:** **Session 4B.18 — the cost proof does not survive being written to disk** 2026-07-30 (ruling verbatim in docs/04 2026-07-30; narrative in `docs/closeouts/4B.18.md`). 4B.17's A4, taken alone; A1/A2/A3/A5 named and LEFT. **§5a.55 IS DISCHARGED and §5a.23's discharge is re-closed after being re-opened on the monolithic path (§5a.63).** Item 1's enumeration over the EMITTERS found the loss is **25 records across FOUR classes, not one**: `record_event` and `register_input`/`register_output` hardcode `subjects=[]`, so **every Event and Artifact the system emits is subject-less**, and `load()` rebuilt `_all_evidence` from `entity_records` alone — 236 built -> 211 loaded on a real monolithic run, taking the entire input manifest and the four M0 conformance rate Metrics with the solver report. A subject-less Finding survived in `finding_index` but not `_all_evidence`, so **one loaded index gave two answers about itself**. Fixed at the ROOT: **schema 2 persists `_all_evidence` and DERIVES the indices on load** through `build`'s own `_index_record` (and is 0.94x the size). The invariant: **a persisted index is a faithful reconstruction of the index it was saved from, or the load reports itself INCOMPLETE and names what is missing — silence is forbidden.** `CostProof` gains a fourth state, `unreadable`, so a claim about the PLANT can never be manufactured from a fact about our STORAGE. Old indexes load and declare themselves; forward compatibility is NOT provided and is named. The round-trip guard asserts by **kind and count**, emits through the real Reporter, runs over all 14 real runs, and its **negative control is proven red (19 failed / 7 passed)**. Verified on the re-minted pinned world (**both clean items returned**), a migrated monolithic board (**the 29,390.52 gap item, ranked second**), an unmigrated artifact, and the money rider on both. One defect, one fix.

**v2.63:** **Session 4B.17 — run the bank** 2026-07-30 (docs/04 session amendment; narrative in `docs/closeouts/4B.17.md`). A measurement session: recalibrate, grade, triage, **fix nothing**. **§5a.22 IS DISCHARGED (§5a.54)** — `regression_founder_r5`, committed 4B.5 and carried unrun for six sessions, is calibrated against the pinned world's PERSISTED document, extended 27 → 33 questions with six unbanked specimens added verbatim, and run **six times** (three on shipped defaults, three on Haiku-everywhere; 198 answers). Every expectation change is logged in `tests/ai_exam/RUBRIC.md`'s append-only RECALIBRATION LOG with its cause and its old text; the question text of all 27 originals is untouched; the bank was calibrated BEFORE its first run so there was no output to fit to. **NOTHING IS LATE ON THIS BOARD**, which turned nine lateness questions into false-premise specimens — and **the card specimen DEGENERATED**, because 4B.7 made `reopt_delta_abs` 0.00 by construction (§5a.12) so move equals total and "which half did you quote" can no longer discriminate. **FIVE TRUTH FAILURES, ALL REPRODUCIBLE:** two authored door labels assert facts about the board without reading it — the product offers to *"explain why CUT-01 carries no work"* about the **busiest machine in the plant** (§5a.60); the no-such-machine correction lists **8 of 15** machines as "the machines here are", omitting the one the asked order is actually on (§5a.54, and visible verbatim in 4B.13's own close-out); **the synthesis toolbox reports the merged elapsed SPAN as `duration_minutes` and as `busy_minutes`** — 5821 where the truth is 1501 working minutes, 3.9x the machine's total open time in that span, the **fourth seam** of a class fixed three times (§5a.56); **the pinned exam world cannot state its own cost proof** because `EvidenceIndex.save()` drops run-level records, so the strip says PROVED and the answer says "no solver report I can read" (§5a.55); and the evidence chain under `why-on-machine`'s only-eligible lead **contradicts it and still carries the founder's original vacuous driver phrase** (§5a.54). **THE TIER QUESTION IS NOT RESOLVED, AND NOW THE REASON IS STRUCTURAL: 31 of 33 questions never reach the layer the split changes** (§5a.57) — across 198 answers the two configurations differ in ONE routing decision, which is the parse's, and the parse is Haiku in both. Cost $0.0105 vs $0.0110 per question, with **Sonnet the cheaper of the two here**. Also: the `repeat`/`deaf` boundary is keyed on string identity so a rephrased re-ask gets self-doubt and the terseness specimen never fires (§5a.58); §5a.51's "off board selection" claim does not reproduce (§5a.59); the coaching invitation **cannot decline to fire, by shape** (§5a.61); the binding-family census is empty on this board and not derivable from the document (§5a.62). No solve, no contract change, no product module touched.

**v2.62:** **Errand 4B.16a — the key, and whether the parse reaches the new routes** 2026-07-29 (narrative in `docs/closeouts/4B.16a.md`). **§5a.7 IS CLOSED AND WAS A RUMOUR FOR THREE SESSIONS** — it cost six sessions of "the r5 bank is key-blocked", then 4B.15's discovery that the exam harness always had its own loader, then 4B.16 citing it a third time to explain two unmeasured routes. Read plainly, by code rather than by trying again: **the sweep tool was NEVER blocked** (its own repo-root-anchored loader since 4A.5b, commit `f3bb319` — proven live this errand, parser available, 1319 ms, graded 1/1); **pytest was, for one session**, fixed by 4B.8 and re-verified here (four slow tests, 54.7 s); and **`python -m mre.ask` / `python -m mre.ai_exam` had NO loader at all**, so from a bare shell the harness's own front door built an unavailable parser and answered on the honest could-not-interpret floor — indistinguishable from a missing key, and the reading that kept the entry alive. **THE MECHANISM WAS NEVER THE KEY AND NEVER ONE READER:** nothing in the library loads a file (correctly — in a container the key comes from the platform secret store), so every ENTRY POINT populates the environment itself, and the repo had **four independent implementations** of that step plus two front doors with none, one copy already DRIFTED to `os.environ.setdefault` (which writes an EMPTY value where the others skip it). **`src/mre/env_local.py` is now the ONE reader**, with a guard test that goes red on a second one and a proven negative control. **BOTH 4B.16 ROUTES REACH A PLANNER'S PHRASING (§5a.51)** — nine of ten phrasings live on the pinned world, all four `briefing` cold opens at 0.95; the single miss (`"why can't it be earlier"` → `why-here`, negative polarity) is a genuine route boundary and was NOT fixed. **THE MEASUREMENT FOUND A LEAK IN THE INSTRUMENT:** `RESET` cleared four conversation channels and missed the fifth, so the deafness rider scolded across conversation boundaries for seven consecutive turns, citing discarded questions — `forget_deliveries` is the symmetric clear and the runner now calls it. **THE OPENER'S SCAN IS 4% OF THE TURN (§5a.52)** — 61.0 ms dispatch of which 58.7 ms is the scan, against a 1251 ms parse; precompute measured both ways (0.4 ms cached) and LEFT, with the contract shape and the pilot-scale reason to revisit named. **THE COUNTERFACTUAL'S SPEC CITATIONS DODGE §5a.48 DELIBERATELY (§5a.53)** — `SPEC_OF` is authored constants complying with §5a.48's own prescription, written one commit earlier; the prohibition on refactoring them into a corpus lookup is now recorded where a refactorer reads it, and the spec-citation kind is still owed for the synthesis tier. No solve; the pinned world untouched; no contract change.

**v2.61:** **Session 4B.16 — the counterfactual and the opener** 2026-07-29 (docs/04 session amendment; narrative in `docs/closeouts/4B.16.md`). Two questions a planner asks NEXT, neither of which had a route. **THE COUNTERFACTUAL (§5a.49)** — `what-would-change` joins the vocabulary (parse prompt **v13**) as the INVERSE of 4B.14's blocker analysis over the SAME computed bounds and no new ones: take the family that BINDS and report the change that would move it, with its threshold and the arithmetic. **EVERY THRESHOLD IS VERIFIED BY RE-RUNNING `earliest_fit` UNDER THE HYPOTHETICAL**, and the verification applies R-C3's degenerate-split rule — which is how the session found that the brief's own worked specimen (`min_chunk <= 240`) **does not work**: the computed ceiling is **215 = floor(431/2)**, because at 216 the solver treats the operation as atomic again. **NECESSARY, NEVER SUFFICIENT, ENFORCED BY SHAPE**: every answer names the NEXT BOUND that would apply once the barrier is gone, recomputed through the tail of the ladder rather than assumed to be the runner-up. The B1 lever is COMPUTED — other eligible lanes are scanned from the same upstream floor, and on the pinned board the honest answer is that PAINT-01 is the only one. B7/B8, the objective and a declared closure are NAMED as unpriceable rather than estimated. **THE OPENER (§5a.50)** — `briefing` widens from the 7am triage to the whole-board read: every item the document supports, **ranked by consequence**, each carrying its own number and a pointer to the question that opens it up, as contracted testimony with no synthesis on the path. The ranking rule is STATED (band 1 is money and its two members are comparable because both are currency); **"three things and none of them are on fire" is reachable** because a proved optimum and an empty late list are reported as reassurance; eligibility is what makes a busy machine a concentration rather than an observation; and what the document does not support is REPORTED, never omitted. Measured on two real boards; concentration did not fire on either, because demo density runs far below the threshold. No solve; the pinned world untouched.

**v2.60:** **Errand 4B.15a — ship the tier split** 2026-07-29 (narrative in `docs/closeouts/4B.15a.md`). §5a.44's recommendation was RULED and is now the shipped default: **the parse constructs on Haiku, synthesis on Sonnet 5**, resolved at construction time from **THREE SEPARATE CONSTANTS** (`llm_compat.parse_model` / `synthesis_model` / `voice_model`, each with its own env override). A single shared MODEL dial cannot express a split and would un-ship the measurement as a tidy-up — `tests/test_model_tiers.py` forbids it, and also pins that the shipped synthesis default is a model `llm_compat` can build a VALID request for, which is not decoration (§5a.44's `temperature=0` finding is exactly a default nobody could call). **THE THIRD CONSTANT IS THE VOICE** (`LLMRenderer`, which rewords an already-validated answer): it was not in the bench, it did not move, and it is now named so it cannot be swept along by a grep for the old literal. **LATENCY IS THE COLUMN THE BENCH SUMMARY DROPPED (§5a.46)** — the shipped split's p90 is **23.1s** against Haiku-everywhere's **14.6s**, while the median barely moves (2.1 → 2.3s); live, end to end on the shipped defaults, synthesis answered in **9.9 / 16.2 / 18.1s** against **1.7s** for contracted routes. The gap between those two columns is the whole story: a demo on contracted routes feels identical, and a demo asking the open questions waits 10–20s an answer. **THE TAIL IS NOT THE MODEL CLASS** — every tier's p90 is 6–9× its median, which is the second tier's multi-step tool loop; a cheaper model runs the same steps faster, not fewer. **THE QUALITY RANKING DID NOT REPRODUCE ON ANY COLUMN** — two runs of the same 15 questions against the same world (Opus 14/15 → 10/15, Haiku 13/15 → **14/15**, the split 14/15 → **13/15**, below Haiku-everywhere on the second run); only cost reproduced. The honest statement of the case is "the bank can resolve the cost, not the quality difference," and that limit travels with the decision. **A SYNTHESIS ANSWER THAT READ NOTHING DOES NOT SHIP (§5a.47)** — §5a.44's fabricated-machines specimen is closed by three deterministic conditions with no model judgment anywhere, at the one delivery seam, failing OPEN in every direction; the negative control proving an honest no-tools answer STILL SHIPS is the test that matters most, because without it the guard is a mute button and the honest floor is the first thing it eats. **NEW DEBT: §5a.48** — a corpus-grounded claim cannot carry a `[record:]` citation, so an answer quoting a spec VERBATIM is labelled "my reading, no record states this" and reads weaker than an inference over placements. No solve; the pinned world untouched; **no fixture, golden or test pinned a model string** (enumerated exhaustively, not assumed — the recorded exam sweeps carry the old literal as OUTPUT and were deliberately left alone).

**v2.59:** **Session 4B.15 — give the reasoner the manual** 2026-07-29 (docs/04 session amendment; narrative in `docs/closeouts/4B.15.md`). **ITEM 0 SETTLED: 4B.14's CLOSE-OUT IS RIGHT AND THE FAULT IS DATE RESOLUTION (§5a.45)** — PAINT-01 is OPEN on Tue 2026-01-13 and carries ZERO work; the live answer's "07:00 to 11:24" is real contiguous occupancy on Tuesday **2026-01-06**, the other Tuesday in a five-Tuesday horizon. A true fact about the wrong day, because neither governed prompt carried a reference date. **A MATCHED ROUTE COULD NOT BE WRONG (§5a.40)** — five consecutive measured turns were swallowed by `coaching` at 0.92 confidence; `route_falsifiability` now checks the DETERMINISTIC rendering at the dispatch seam and falls through to synthesis on subject-silence or a discarded disjunction. It can only REJECT a route, never name one. **THERE WAS NO ROUTE THAT READS A FIELD (§5a.41)** — `attribute-lookup` joins the vocabulary (parse prompt **v12**); the field vocabulary is REFLECTED off `contracts/entities.py` and the provenance chain is walked to the submission column. **CAPABILITY CLAIMS GROUND IN docs/05 OR ARE REFUSED (§5a.43)** — the catalog's own markdown TABLES are parsed into 26 records + 6 rulings + 6 exclusions, discharging the prose-locked debt for the catalog rows; the honesty register is DERIVED from (verdict, status) and "can two machines share one operator" now agrees with the blocker analysis's own not-weighed list. **THE REPEAT DETECTOR WAS INVERTED (§5a.42)** — four measured firings, zero true positives; the signal is now the delivered ANSWER, not the route, and the scold is deleted. **THE CORPUS SHIPS WITH THE BUILD, IN TIERS (§5a.39)** — docs/07 is reachable by NOTHING, docs/04 is opt-in and every passage dated (15 undated sections DROPPED, fail-closed), and the committed index carries a sha256 per document so a spec edit without a rebuild is a red test. **THE TIER IS MEASURED (§5a.44)** — and the ask path could not run on Opus 5 or Sonnet 5 at all until `llm_compat` landed, because both call sites hardcoded `temperature=0`. Recommendation: **parse on Haiku, synthesis on Sonnet 5** — ties best correctness and multi-hop, lowest median latency, 37% under Sonnet-everywhere and 62% under Opus-everywhere. Synthesis prompt **v3**. No solve; the pinned world untouched.

**v2.58:** **Session 4B.14 — why is it here: the blocker analysis** 2026-07-29 (docs/04 session amendment; narrative in `docs/closeouts/4B.14.md`). **ITEM 0 RETURNED READING (A): THE SCHEDULE IS RIGHT, THE EXPLANATION WAS WRONG** — ORD-000013's op20 is not splittable, needs 431 working minutes and had 294 left before PAINT-01 closed on Tuesday; Wednesday is a plant-wide `planned_maintenance` closure (13 of 15 machines, HEAT-01/02 excepted); Thursday is the first window long enough. The session did not halt. **THE EXPLAINER KNEW ONE CAUSAL STORY AND THE PLANT HAS SIX (§5a.35)** — `why-here` computes an earliest-feasible-start per docs/05 family (A4, A1/A2, R-F1, A7/F1, B1, C1/C2, C3), names the family that binds, and draws the distinction the product could not: **COULDN'T versus CHOSE-NOT-TO**. Four families are NAMED as uncomputed on every answer rather than silently omitted. **CAUSAL SUFFICIENCY (§5a.36)** — a cited cause must account for the quantity it explains; the vacuity tripwire passes this class cleanly and neither check subsumes the other. **THE ROOT CAUSE WAS A THIRD FIRST-CHUNK-ONLY READ (§5a.34)** — the explainer's row model reported a chunked operation's first PAUSE as its end, the exact figure the bad answer cited; 4B.13 fixed the same class at two other seams and stopped. **DISAGREEMENT LAUNDERING (§5a.37)** — a challenge to the reasoning was re-parsed into a question about lateness and answered "yes, the record agrees"; `ContestedClaim` lets the parse say which claim is disputed and a `timing` contest is answered by the blocker analysis. **THE "WHY IS THIS HERE?" BUTTON WAS ASKING A DIFFERENT QUESTION (§5a.38)**, plus the transport-error turn, the fused lane citations and the selected-operation scope. Contract **1.12** (the R-C3 pair on the job card, both Optional). Parse prompt **v11**.

**v2.57:** **Session 4B.13 — clear the board for a cold stranger** 2026-07-29 (docs/04 session amendment; narrative in `docs/closeouts/4B.13.md`). Not a feature session: it removed the things that would tell a first-time user the software is lying or unfinished. **THE DOWNTIME BAR IS A RENDER MERGE, NOT A PHYSICS VIOLATION** — the canonical Assignment carries three run windows (1501 working minutes) and NO assignment interval anywhere on the board overlaps a closure; `assemble_rolling_document` collapsed them to one chunk because `RollingView` placements carried no chunk data, and the cockpit has drawn per-chunk pieces since CU5. It hid the pauses of every chunked op on every rolling board, **which is how a real violation would have stayed invisible**; `tests/test_rolling_chunk_fidelity.py` is now the test that can tell the two apart. **VERIFICATION IS DOWNSTREAM OF TOOL VOCABULARY** — `lateness_set` counted 14 unplaced tray orders as "on time or early", synthesis repeated it faithfully and claim verification PASSED it, because the count really was what the tool said; a tool that fuses two categories makes every claim built on it unfalsifiable-but-verified, so the fix is in the TOOL and the verifier did not change. **THE RELEVANCE GUARD, two clauses, both FLOORS** — a false "why is X on Y" premise is now CORRECTED with evidence instead of echoed (a stranger mistyping a machine name got a fluent falsehood with an evidence chain attached), and a predicate the answer never addressed is ADMITTED at the delivery seam; `predicate_coverage.py` never routes, never suppresses, never changes a figure. **§5a.29 DISCHARGED** — `solve-optimality` joins the closed vocabulary (parse prompt **v10**), answering from the same M6 record the strip chip reads. Machine count no longer calls declared resources working. **New debt: §5a.33** (four slow fixtures broken since 4B.8). Close-outs now live at `docs/closeouts/<session-id>.md`, one path per session.

**v2.56:** **Session 4B.12 — where the cliff actually is, and whether a hint moves it** 2026-07-28 (docs/04 session amendment; narrative in `SESSION_CLOSEOUT.md`). A MEASUREMENT session, no ruling. **The cliff is at 92 ops/machine, not 137** — re-run against byte-identical worlds, R-PD1's admitted past-due work puts tardiness into every density and the proof costs 200–360× what it did (§5a.31, superseding §5a.27's numbers by a dated note rather than a rewrite). **F004 and F006 are SOLVED, not bracketed** — 83.5–85.8% and 98.8% gaps — but **not one cell at any density returned UNKNOWN**, so the engine's problem at real density is proving an answer, not producing one. The warm start (§5a.32) ships behind a flag, DEFAULT OFF: it is a re-roll, paying in the cliff region and costing beyond it.

**v2.55:** **Session 4B.11 — the honesty bundle: the proof rendered, the late work scheduled, the arithmetic reconciled** 2026-07-28 (docs/04 session amendment with **R-PD1 verbatim**; full narrative in `SESSION_CLOSEOUT.md`). Four things a customer meets in the first hour, two of them coupled: **R-PD1 makes real boards tardiness-dominated, which §5a.27 proved is exactly the regime where the cost proof fails** — so the status had to become visible in the SAME commit that started scheduling late work.

**R-PD1 — PAST-DUE DEMAND DISPOSITION, ruled and implemented (docs/04, verbatim).** Six clauses. **(1) PAST-DUE IS WORK, NOT A DEFECT** — admitted, scheduled, priced with tardiness from its declared due date. **(2) EXCLUSION IS A DATA-DEFECT CATEGORY ONLY** — never for a true statement about the plant's position (late, beyond horizon, over capacity); this **generalizes §5a.1 and §5a.26 into one rule**. **(3) THE GATE'S DISPOSITION BINDS DOWNSTREAM** — a module that removes a `proceeded_flagged` demand raises its OWN finding naming ITSELF. **(4) TARDINESS DECOMPOSES AND NEVER FUSES.** **(5) AGE IS NOT LATENESS** — **OPEN, deliberately unbuilt** (§5a.28). **(6) EVERY PER-ORDER ROUTE VOICES THE DISPOSITION.**

**21 of 21 past-due orders are now SCHEDULED on the specimen**, and **gravity did not have to be told**: measured, they are admitted by the BASE rule (`due <= window_end`) unconditionally, before gravity runs at all — **the admission policy needed no change and did not get one**. `validator.py` Check 1 excludes nothing and raises one `PAST_DUE_AT_INTAKE` finding (**finding code 19**, added never repurposed — `TEMPORAL_IMPOSSIBILITY` is M0's verdict on `due < release/created` and keeps that meaning) at INFO / `proceeded_flagged`, with `remediation_applies: false`. **A SECOND EXCLUSION SITE was found and closed:** Check 5's resumable window-fit test floors `elapsed_days` at 0, so every past-due resumable demand would have fallen straight into it and been excluded as `INFEASIBLE_SUBSET` — the same removal wearing a different code. And **scheduling past-due WORK must never mean modelling past TIME**: `_compute_horizon`'s reference-date floor now applies unconditionally (sample_data dragged the horizon to **2024-12-20** without it).

**THE TARDINESS SPLIT — contract 1.10 → 1.11.** `cost_summary.tardiness_floor` + `tardiness_controllable`, present TOGETHER or not at all, summing to `tardiness` to the cent, and **ABSENT on any book with no past-due work** (so on-time monolithic documents are byte-identical to their 1.10 selves). **It does not change the model; it makes a decomposition the pipeline already contained legible** — `solver_builder` has always clamped `due_min = max(0, due − horizon_start)`, so the floor was never in the objective. **The brief's stated test for this was the WRONG test and the data said so:** at 60 orders both arms returned FEASIBLE and 237/240 placements differed, which measures two truncated searches, not an argmin. At 12 orders **both arms prove OPTIMAL** and `B − A = 6,999,840 = Σ (weight × floor)` **exactly**; placements still differ (34/48) because that is a **TIE**, not a refutation — `argmin f_B == argmin f_A` as SETS. **Placement identity would have been sufficient but is not necessary.**

**§5a.23 DISCHARGED — the cost proof is rendered and voiced.** `src/mre/modules/cost_proof.py` is the single definition; the cockpit's top strip carries a chip (label + title composed SERVER-SIDE, arriving on `/meta`, so the JS composes no wording) and the answer surface carries an unprompted rider fired by the ONE delivery seam **only when the board is UNPROVED and the text states money** — the asymmetry is the point: the surface volunteers the thing that weakens its own number. Every bundle leaving `Explainer.route` carries the proof, stamped at the one dispatch. **The rolling path could not state a gap at all** until now (`SolverBlock(gap=None)` unconditionally); `RollingView` now carries stage 1's `objective` and `gap`. **No new route was built** — that is a vocabulary-class change, named as §5a.29. **AMENDED 4B.18 — THIS DISCHARGE WAS RE-OPENED ON THE MONOLITHIC PATH AND IS NOW RE-CLOSED (§5a.63).** The discharge was measured on a REBUILT evidence index. Every monolithic board the API serves loads a PERSISTED one (`__main__.py:585` saves it, `api/app.py:1482` prefers it), and schema 1 dropped the M6 `solve_complete` Event on save — so `from_evidence` returned `no_solve`, the rider's `unproved` gate was False, `_proof_items` returned `[]`, and the strip said PROVED beside an answer saying "no solver report I can read". The chip was unaffected because it reads the DOCUMENT via `from_solver_block`, which is exactly why the two surfaces could disagree. Fixed by schema 2; the rider, the opener item and the route each gained an `unreadable` branch, and none of them may be silent.

**THE 42, RECONCILED (§5a.26's undiagnosed observation, closed).** Two compounding errors in `_excluded_summary`: the COUNT came from a **token set** holding both the UUID and the `ORD-` id of every excluded demand (21 × 2 = 42), and `scheduled` counted **every** demand in the snapshot with `total` = that + the exclusions (60 + 42 = 102 in a 60-order world). Display and counting now key on the **resolved ORDER**, because the same order is excluded in two id-spaces by two layers. Invariant asserted: `scheduled + count == total` and `total == demands in the snapshot`. **Proved on a purpose-built world that still HAS exclusions** — R-PD1 dissolves the note on the specimen itself, so covering it was not assumed. A third defect fixed at its own site: `finding_subject_label` appended the evidence's raw `demand_id` even when the subject had already resolved.

**THE THREE MEASURED FALSE ANSWERS ARE FIXED AND PINNED** (`tests/test_pastdue_disposition.py`, 35 tests): "where is ORD-X" no longer says "Nothing scheduled"; "why isn't X scheduled yet" no longer offers a disjunction **neither branch of which was true**; "which orders are already late" no longer says "No late orders found" in a world 35% past due — it lists 21 with the clause-(4) split per line.

**THE sample_data BASELINE WAS REGENERATED, and the brief's premise was wrong.** The acceptance criterion assumed no monolithic golden carries past-due work; **sample_data carries WO-PAST-001 as seeded defect 3** — whose `DEFECTS.md` entry has declared `proceeded_flagged` all along, while the implementation had drifted to `excluded`. **Accounted for by construction:** re-running the gate pipeline with that single row REMOVED reproduces the previous golden **byte-for-byte** and its ledger to the cent (24,769.00). New golden **801,930.00**, tardiness **777,521.00** — of which **776,160 is FLOOR**, which is the clearest possible argument for 1.11. `pilot_scale` and every rolling golden are untouched. New/updated debts: **§5a.28** (clause 5 open), **§5a.29** (no optimality ROUTE), **§5a.30** (`facility_real`'s CONDITIONAL grade is a generator truthfulness defect, correcting 4B.10).

**v2.54:** **Session 4B.10 — the real shape: few machines, deep queues** 2026-07-28
(docs/04 session amendment; full narrative in `SESSION_CLOSEOUT.md`). **First act:
4B.9's measured book made DURABLE** in §5a.24 — it had lived only in a close-out.
**§5a.25 — LOAD, NOT OP COUNT.** The duration semantics are **DETERMINED, not
ambiguous**: `op = SetUpMinutes + (WoQuantity/CostingLotSize) × ProductionMinutes`,
per operation, agreed by `legacy/Formatnewjobs.py:68`, the standing
`legacy_author_definition_v1` ruling, and the data itself (log-log **r = +0.683**).
**A SENTINEL CLASS CARRIES 93.56% OF THE COMPUTED LOAD** — 1,434 products reading
`lot = setup = production = 1`, all three exactly 1 on **100.0%** of rows, and no
exclusion rule we have would catch them. Utilisation is **BOTH answers**: F006, the
LARGEST facility, is at **112.5%** (structurally over-capacity — no solver fixes
that); F004, the MEDIAN, is at **32.6%** (comfortably feasible — **there the
difficulty is ours**). **§5a.26 — PAST-DUE WORK VANISHES and TWO MODULES DISAGREE**:
M0 flags 21 of 21 `proceeded_flagged` (CONDITIONAL, `go=True`), M3's validator then
EXCLUDES them, and nothing reconciles the two; they appear nowhere in a 111,839-char
document and only the aggregate route reaches them — filed as "**21 data-quality
problem(s)**", the same shelving error §5a.1 names for `--horizon-days`. **§5a.27 —
THE CLIFF IS THE ONSET OF TARDINESS.** On the real shape the cost proof is lost
between **94 and 137 ops/machine**, *below* F004's real 246 and far below F006's
803: **the gap probe's verdict does NOT survive the objective change, and not in the
direction hoped.** Utilisation is REFUTED as the predictor — at identical
utilisation and identical ops/machine the two alternate arms differ **165×**.
Alternates buy 0.93→1.44% of ledger for 3×→52×→**165×** the proof effort.
`facility_real` added (4 variants, calibration checked by a tool, MEASURED-vs-AUTHORED
provenance); **`pilot_scale` byte-identical to HEAD.**

**v2.53:** **Session 4B.8 — the budget split, the status ruling, and why 14 days returns
nothing at 200 orders** 2026-07-28 (docs/04 session amendment; full table in
`SESSION_CLOSEOUT.md`). **Pre-flight: the missing API key was LOADER WIRING** — `.env.local` was
present the whole time and nothing on the test path loaded it (`tools/run_ai_exam_sweep.py`
carried the repo's only loader). One conftest loader; **the four blocked slow tests pass in
40.6 s**; no `skipif`, no assertion weakened, the r5 bank still not run. Four OTHER tests had
been passing only because the key was ambiently absent and now CONTROL it explicitly (§5a.7).
**CU1 measured three budget policies before changing anything** (6 instances × 5 seeds): the
current fixed split **loses the COST PROOF at 200 orders** (two seeds need 4.542/4.962 units
against a 4.0 cap → ledger 35,127.05 vs the optimum **27,863.63** that the alternatives prove
5/5 with **zero** seed spread), while a plain cost-first remainder hands stage 2 **ZERO on 5/5
seeds at 120 orders** and silently retires the tiebreak. **Shipped: P3** — stage 1 capped at the
total minus a 1/12 RESERVE, stage 2 given the remainder. `_STAGE2_DET_TIME_S` **DELETED** from
both twins; `det_time` **RENAMED** `det_total` so every caller had to state its own historical
total (no single multiplier preserved them). **CU3 is a RULING, not a fix:** the existing status
field carries **stage 1's COST proof**, new optional fields carry stage 2's TIEBREAK proof —
contract **1.9 → 1.10** — so a schedule whose cost is provably optimal finally says so instead of
reading FEASIBLE. **CU4** made the dead `EARLINESS_PREFERENCE` attribution DORMANT after checking
the fallthrough is better (CAPACITY_BLOCKED carries real occupancy evidence since 4B.5 CU3a).
**CU5 diagnosed §5a.15 and stopped: THE 200-ORDER / 14-DAY INSTANCE IS FEASIBLE** — a solution in
**0.082 deterministic units** once the objective is dropped, so it is NOT an R-SC2 admission
defect. Build time is 0.05–0.19 s and ops-per-machine peaks at 92, killing both standing
hypotheses; the cliff sits between 8 and 9 days at 200 orders, and is **NOT general** (200 orders
proves optimality at 123 free ops while 120 orders fails at 115). **Discharged: §5a.19, §5a.21.**
**Goldens did NOT move** — the rolling digest and every asserted figure unchanged, sample_data
byte-identical, the 40-order board still 16,481.95 / tardiness 0.00. New debt: **§5a.23** —
"provably optimal" is now a claim nothing voices (an R-AI1 debt, named not built).

**v2.52:** **Session 4B.7 — the earliness price is removed from the objective** 2026-07-27
(docs/04 R-SC3 AMENDMENT, verbatim; full table in `SESSION_CLOSEOUT.md`). **R-SC3(2) — the
declared `earliness_value` as a PRICE in the primary objective — is RETIRED.** R-SC3(1) stands
and is now genuinely implemented: the two-stage solve IS the tiebreak, and **stage 2 runs
unconditionally** at every coefficient including 0 and undeclared. **Item 1 measured the arm
4B.6c never ran** — staged cost-only (**A0s**), six instances × five seeds at the shipped
4.0/2.0 split. It reproduces the cost-only PROVEN OPTIMUM to the cent at 5/8/15/40 orders
(OPTIMAL 5/5, seed spread zero) while spending **45.53% fewer start-minutes** at 40 orders.
Condition (ii) PASSES (strict start-sum wins on 5 of 6 instances). Condition (i) splits: the
UNITS claim the cap actually guarantees — stage 2's ledger ≤ stage 1's, within a run — holds
**30/30**; the literal A0s-vs-A0 inequality fails on **4 of 30 seeds**, and the cause is proven
to be the **budget split**, not the units (at 200o w7 A0 needed 4.542 / 4.962 deterministic
units to prove optimality on exactly those seeds, against stage 1's 4.0 allocation, and matched
A0s to the unit on the three seeds where its proof fit). **NOT halted**, because the brief's
halt was conditioned on a defect the measurement disproves. The coefficient parameter is DELETED
from both solve signatures rather than defaulted to 0; `earliness_value` survives as a REPORTING
rate that values the start-minutes the tiebreak recovered, on its own labelled line, never in a
cost figure — **and the SCHEDULE is asserted byte-identical across 0 / declared / 100× declared**.
**Discharged: §5a.16** (rolling now returns stage 1's COST objective with stage 2's placements,
copying the monolithic twin), **§5a.17** (5% is 5%, was 40%), **§5a.12** (`reopt_delta_abs`
−11,975.83 → **exactly 0.00**, by construction, not by relabelling), **§5a.9** (the regenerated
40-order board sits at the proven optimum 16,481.95 / tardiness 0.00, so the ~7.9%-dearer
incumbent is gone). Fixtures regenerated under authorization, every figure accounted by
operation identity, reproducing across PYTHONHASHSEED 0/1/2. New §5a debts: **19** stage 2's
fixed 2.0 budget is misallocated, **20** the EARLINESS_PREFERENCE driver now names a mechanism
that no longer exists, **21** the reported window status is stage 2's tiebreak-proof, **22** the
r5 bank's card expectations are invalidated again.

**v2.51:** **Session 4B.6c — measurement: does the zero-cost tiebreak cost us?** 2026-07-27
(docs/04 session amendment; full table in `SESSION_CLOSEOUT.md`). A MEASUREMENT session: its
product is a table. No shipped objective changed, no ruling amended, no golden or fixture
moved, no module in `src/` touched; ONE test committed (`tests/test_objective_units.py`).
**THE VERDICT: candidate B COSTS US — `BIG · cost + Σ starts` degrades CP-SAT's search badly,
and the hour-granularity variant does not rescue it above 15 orders.** Five arms (cost-only,
the shipped status quo, B, B-at-hour-granularity, B-at-10×-BIG) × six instances × five seeds,
at a deterministic budget of 6.0 identical on every arm; 151 runs (148 comparable, all
producing a ledger, plus 3 excluded probes), zero wall-truncated.
Against a cost-only arm whose seed spread is **exactly zero**, B's median ledger is **+69.02%**
at 40 orders, **+39.50%** at 200 orders (7-day window) and **+1354%** at 15 — and at 120 and
200 orders B is *also worse on sum-of-starts* than having no tiebreak at all. **BIG is not the
mechanism** (10× BIG is identical to the cent on every shared seed); the mechanism is that a
zero-tardiness cost objective is START-INDEPENDENT, so cost-only is a feasibility problem
CP-SAT closes in **1.7% of its budget**, and any start-sum term turns it into an optimization
it cannot close in 60× that. The correctness check passes with **no defect** (where both prove
OPTIMAL the ledgers are identical, 7/7). The **status quo's own damage** is measured on the
same axis — **+73.20%** at 40 orders, **+97.61%** at 120, almost all of it tardiness — which
extends §5a.12 from the fixture to every instance above ~15 orders. Also measured: a scratch
sequence-preserving compressor (56 runs, 1 rejected shift at +$151.67, ledger never rose,
56/56 re-validated OPTIMAL by CP-SAT) that moves **nothing** on proven-optimal schedules and
takes **−16.7%** off a budget-truncated one. New §5a debts: **15** the shipped 14-day window
is budget-starved at 200 orders (UNKNOWN at 6.0 *and* 20.0 units), **16** the rolling path
records a MINUTE COUNT as its solver objective (a defect, pinned), **17** the pool's cost
bound is looser than its stated tolerance under a declared `earliness_value`, **18** R-SC3(1)'s
price, now measured.

**v2.50:** **Session 4B.6b — errand: four answers** 2026-07-27 (docs/04 session amendment).
A FINDINGS session; its product is knowledge. One behaviour changed, everything else was
measured and left alone. **Item 1 — the baseline delta is a MEASUREMENT, not an identity, and
neither reading in the brief was right.** `baseline_total_cost` includes the tardiness term
(same ledger code as the incumbent, `extractor.py:390`) and it is NONZERO on an unrelated
instance (200 orders: baseline tardiness 361.67, `baseline − (incumbent − tardiness)` =
**+405.42**), so the MECHANICAL reading is falsified empirically and by code-read. But the
BENIGN reading's premise — "the incumbent is simply poor" — is false too: the budget probe
shows the gap does not close at 2×/4×/8× the deterministic budget (it is DEARER at 8×). The
actual cause is an **OBJECTIVE MISMATCH**: the rolling window solve minimizes
`cost + earliness_coeff · Σ starts` (the plant's DECLARED `earliness_value` = 0.05 $/min,
R-SC3) while the sandbox baseline's `SolverBuilder` minimizes cost ALONE, and the extractor's
ledger carries **no earliness line at all**. Forcing `earliness_value = 0` drives
`reopt_delta` to **exactly 0.00** on the shipped fixture. **4B.5's headline fix does not
reopen** — the MOVE half is apples-to-apples (both the pinned re-solve and the baseline run
under the earliness-free objective); it is the LABEL on the other half that is wrong (§5a.12).
**Item 2 — canonical ids SURVIVE a new submission.** Under `identity_v1` the derivation is
closed-form `Demand = f(order_id)`, `Operation = f(order_id, route_id, product_id, sequence)`
with no submission id, run id, reference date, timestamp or row ordinal anywhere. Three
consecutive-day submissions with real data deltas accrued **78 cross-submission realizations**;
all 33 demands predicted by more than one run share op ids. Splicing seam 3 is NOT blocked on
an IDS-identity key. The open seam is RETIREMENT, not identity (§5a.13). **Item 3 — the one
fix.** `tools/build_rolling_exam_run.py` now builds a coarse zone for the harness fixture and
requests `coarse` (and an explicit `reference_date`) on the registered solve; the exam world
verified carrying a contract-1.9 `coarse_zone` with all 14 tray items coarsely placed. The
exam runner's synthesized delta card is replaced by the SHIPPED card, figure for figure
(§5a.10). **Item 4 — the data-root sweep is a CORRECTNESS debt, not a performance one**: two
plants with overlapping order numbering in one data root produced **20 cross-plant
realizations** (§5a.8). **Item 5** — the 4B.6a count discrepancies reconciled: `test_coarse_horizon.py`
added **10** tests, not 11 (the suite's 1614 -> 1624 was exact and the close-out over-counted
by one), and the cockpit ladder collects **227**, not 225 (the one red in a full run is the
standing 4A.3 due-marker flake, re-verified green in isolation). **Nothing was removed and
nothing is silently skipped** on either side.

**v2.49:** **Session 4B.6a — consolidation: the history is wired, the exclusions are voiced,
the goldens move once** 2026-07-27 (docs/04 session amendment; docs/06 v0.6a). **No new
capability.** Three carried debts stop compounding and one measurement lands. **CU1** — the
coarse PREDICTION STORE is wired into the rolling worker (`record_roll_history`), so history
actually accrues: three consecutive rolls on pilot_scale wrote **228 predictions and 180
realizations**, with both intake paths captured end-to-end (**62 natural roll, 38 gravity
admission** at roll 1) and each prediction judged exactly once. Three constraints tested: the
document is **byte-identical with the store on and off** (only `run_id`/`schedule_id`
normalized), a store write failure **loses no schedule and is surfaced** on the run record, and
realization capture fires on both intake paths through the worker. Two named request fields
made it possible: `SolveRequest.coarse` (opt-in per solve) and `SolveRequest.reference_date`
(without it every solve rendered the same window and **the plant never rolled**). **CU2** —
every capacity answer, and every density-band cell tooltip, now names the **uncounted
population** (excluded ops consume zero coarse minutes, so load is understated); both
directions tested, no caveat invented when nothing is excluded. A plant that declares **no
capacity margin** gets a loud declaration note on the certificate, the band and every answer —
and it is **NOT a gate finding**: no rule fires, no verdict moves, the registry stays at **36
rules**, and the entry is an informational remediation note in docs/06 §5.9. **CU3** — the
coarse model's BINDING behaviour is pinned at 200 orders (404 ops modeled, peak utilization
0.998, 123 buckets of tardiness, rho 0.5 INFEASIBLE with the population unchanged); the
40-order guard could have passed with the capacity constraints removed. **CU4** — the rolling
cockpit fixture was regenerated under one-time authorization with **every moved figure
accounted for** (contract 1.8 → 1.9 additive fields, or the 2026-07-26 determinism fixes,
proven by an attribution experiment), the fixture now **reproduces across PYTHONHASHSEED
0/1/2**, 4B.5's **synthesized** attribution split is replaced by real solver figures whose
parts are asserted to sum, and the density band gains its first screenshot coverage
(populated / empty / binding-cell tooltip, both themes). `rolling_empty/` moved too and is
disclosed with the same accounting (the empty-band screenshot needs a document that RAN a
coarse zone and found nothing); `rolling_coarse_hot/` is a NEW fixture, not a moved one.
**CU6** — the resumable exclusion
measured: ~1% of beyond-horizon ops but **5–6% of beyond-horizon minutes**, five times what
the op count suggests; cross-bucket allocation stays a queued refinement. **CU5 HALTED** —
`regression_founder_r5` remains UNRUN for want of an API key (§5a.7).

**v2.48:** **Session 4B.6 — the coarse zone: R-SC2's parked far-horizon clause, discharged**
2026-07-27 (docs/04 R-SC2 coarse-zone amendment + session amendment). R-SC2 closed with
"far-horizon look-ahead pricing: named, parked"; this session builds it. **Beyond-horizon
demand is now coarsely PLACED, not merely listed.** The ruling's seven clauses govern
everything: the coarse model is a RELAXATION, so only the NEGATIVE is ever claimed
(coarse-infeasible ⇒ fine-infeasible, never the converse); the PROOF run (rho = 1.0) and the
PLANNING run (rho declared) are different runs and only the first may prove anything; **rho is
a declared IDS coefficient**, never a constant in solver code; coarse never constrains fine nor
its admission policy; the two ledgers never fuse; coarse renders as LOAD, never as a bar; and
the conformance report is ours to publish. **CU1** — `coarse_horizon.py`: `x[op,res,wk]`
created only for capability-eligible pairs (eligibility carried by VARIABLE EXISTENCE, so an
aggregation error is structurally unrepresentable), real calendar minutes entering as a NUMBER,
coarse precedence, bucket tardiness, and a machine choice that is a **feasibility WITNESS, not
a plan**. **CU2** — contract 1.8 → **1.9**, additive: `BeyondHorizonItem.coarse` +
`RollingBlock.coarse_zone`. `earliest_window_estimate` is UNCHANGED (see the pre-flight below).
**CU3** — the prediction store SHIPPED, not deferred: the document is a window-0 view by ruling,
the audit is cross-roll, so predictions live in an append-only JSONL store keyed
(run_id, demand, op, bucket, witness, run_label), with realization captured on BOTH intake
paths — natural roll and **gravity admission**, the case where two mechanisms on record
disagree about the same job. **CU4** — the RELAXATION GUARD makes clause (1) a theorem (87 ops
mapped, 0 violations) and its **NEGATIVE CONTROL goes red** under a stubbed tightening (13
violations); clause (2)'s necessity is DEMONSTRATED, not asserted (rho = 0.15 returns INFEASIBLE
with 80 of 82 ops still modeled on an instance the proof run places). Cross-hashseed
determinism on both runs. **CU5** — two intents join the closed vocabulary (`coarse-fit`,
`bucket-load`; parse prompt **v9**) and a docked **density band** renders load, never bars;
"when will ORD-X start" gets NO new route — it is already `why-not-scheduled-yet`, now carrying
the coarse bucket beside the due-date heuristic. **No R-AI1 debt is left open.** **CU6** — rho
is pipeline-proven per docs/06 §8 in full: doorway (§5.9 `refinements.coarse_horizon`), gate
rule `ids.coarse_horizon_coefficients_sane` (registry v0.3 → **v0.4**, 35 → 36 rules), adapter
translation with truthful provenance, a pilot_scale truth manifest and an anomaly generator.
**PRE-FLIGHT: two of three tripwires fired.** (1) `excluded_demand_ids` DOES appear in the
rolling path — but only as a READ of the validator's set; no rolling site writes it, so the
disposition story stands, and a test now LOCKS that while it is true. (2)
`earliest_window_estimate` was ALREADY POPULATED by a due-date backoff heuristic with tests, an
AI route and fixture values — the design's premise that CU2 would finally fill it was FALSE, and
overwriting it would have repurposed a live field. Ruled in-session: the coarse bucket sits
BESIDE it. (3) The gravity setup-family-affinity debt was already recorded in docs/04 and here.
**A SECOND FINDING, unasked:** `--horizon-days` writes `excluded_demand_ids` on a PRODUCTION
path — see the carry-forward below. See the docs/04 2026-07-27 amendments.

**v2.47:** **Session 4B.5 — round-five harvest: the card tells the truth about itself,
and the R-F rulings land** 2026-07-26 (docs/04 amendment). **CU1 — DELTA ATTRIBUTION (the
trust item).** The founder's evidence: two different gestures on the same incumbent produced
IDENTICAL delta cards (-$11,975.83, same four affected orders, to the cent). The card
measured the RE-SOLVE and read as measuring the MOVE. Beat two now also solves the same
window under the same budget WITHOUT the pin — the BASELINE, cached per incumbent — and the
verdict SPLITS, always: *window re-optimization* (baseline vs incumbent) and *your move*
(pinned vs baseline), summing EXACTLY to the total. The planner's move is judged against the
baseline, never the stale incumbent; an unprovable baseline shows the unsplit total with an
explicit "includes window re-optimization" line, never a silent fused number. **CU2 — THE
OPEN DELTA CARD JOINS THE RESOLUTION LADDER** (card > board selection > last-answered subject
> history > clarify). `open-card` joins the closed vocabulary (parse prompt **v8**) and READS
THE CARD BACK — it re-derives nothing, so the two surfaces cannot state different numbers.
The founder's "what orders are affected in this move" used to reach `swap-move`. **CU3 — THE
VACUOUS-CAUSAL TRIPWIRE + the why-on-machine audit.** "Because the machine was busy with
other work" was the authored driver phrase carried VERBATIM over a real record — the verbatim
path was intact and the defect was the vocabulary used as a whole causal clause. A
capacity-forced placement now names the eligible machines that were occupied and what held
them (or says the occupancy does not attribute it); every causal route gains a vacuity check
that fails closed to the template. **CU4 — banner + picker repairs:** sticky per-id dismissal,
one offer per newer id, a caret affordance on the picker chip, and `dev_cockpit.ps1` RESUMES
BY DEFAULT (`-Fresh` to mint) so the dev loop stops manufacturing the "newer schedule" noise
the product then has to handle. **CU5 — conversational riders:** an advice push-back naming a
capability routes to that capability's coaching; a route re-fired within two turns varies its
lead; a re-asked count answers tersely with an offer; and per-claim synthesis provenance was
found to be an ANSWER-LEVEL copy and made genuinely per-claim (`read_from` names which tool
calls a sentence came out of). **CU6 — R-F1/R-F2/R-F3 recorded verbatim** (planner-movable
frozen boundary; rush intake as a Demand the solver places; the outcome -> window -> pin
constraint ladder with reasons), plus four NAMED-QUEUED features designed and not built: the
pin register, amend-submission (pilot-relevant), the boundary-drag gesture, and the window
constraint.

**v2.46:** **AI-track Session 4A.5c — R-AI5 part 3: telemetry, the Pareto, the promotion
pipeline. THE R-AI5 ARC IS CLOSED** 2026-07-26 (docs/04 amendment). Implements clauses (5),
(6) and (7) and finishes the residue parts 1 and 2 named. **CU1 — provenance telemetry:**
the question-ledger entry gains a `ParseProvenance` block (intent, ADJACENCY, subject kinds)
because every second-tier answer takes the same route and the route alone cannot tell two
shapes apart; the sweep now WRITES a ledger at all and EMITS the standing report beside the
sidecars (`tools/provenance_report.py`) — residue clustered by adjacency + subject kinds +
DOMINANT TOOL, ranked by a **frequency-weighted Pareto (frequency x verified share)**, with
the clustering method and its known weakness printed in the report. **R-AI5(6) is printed in
the report's own header:** clusters whose residue is takes or aggregate reads are
NOT-PROMOTABLE-BY-DESIGN, excluded from the Pareto, never counted as backlog. **CU2 — the
promotion pipeline, walked end to end as the proof:** the 4A.5b banks were replayed with the
candidate intent DEMOTED (reproducing the pre-promotion vocabulary with the session's own
flag), the report ranked `late-orders|no-subject|lateness_set` first, `promotion_dossier.py`
drafted the application + a draft route on a path nothing imports and validated it against
the pinned world, and the working thread's review put `lateness-cause` into the vocabulary
in one change citing the dossier. The route runs SHADOWED on probation; **demotion is one
field** (the intent leaves `model_selectable_intents()` and the shape returns to synthesis);
promotion is never automatic. **CU3 — the felt bar:** the ask TWO-PHASES (a preflight names
the tier and the panel shows an honest first beat before a ~10s answer, at NO extra model
call — the preflight's parse is remembered and reused); the couldn't-answer floor keeps its
doors; and the **ADJACENT-MATCH GUARD** diverts a matched intent whose stated qualifier it
cannot honour ("next month", "actually working time"), naming the qualifier in the
rendered-by line. **CU4 — the LAST deterministic classifier dies:** `classify_rolling` is
deleted, after its stated prerequisite was built — subject resolution reads the rolling
document's three regions, so **a tray order is never "not in this schedule"**. **CU5 — the
arc-close sweep** (`tests/ai_exam/sweeps/2026-07-26-arc-close/`, 7 banks incl. a new rolling
bank against a new pinned rolling run): totals in docs/04. The working thread returns to the
4B mission.

**v2.45:** **AI-track Session 4A.5b — R-AI5 part 2: labeled synthesis, claim-level
verification, and the provenance surface** 2026-07-26 (docs/04 amendment). Part 1 left an
unmatched intent at an honest dead end; R-AI5(2) always meant it to be a TIER. **CU1 — the
read-only tool surface:** a CLOSED 11-tool evidence-query set (`contracts/synthesis.py` +
`modules/evidence_tools.py`) built as thin wrappers over the same readers the contracted
routes use, with typed results whose ROWS CARRY THEIR RECORD IDS, a stated budget (12 calls
/ 90s / 60 rows) whose exhaustion yields an honest partial, every call logged with its
arguments, and a second GOVERNED prompt artifact (`synthesis_prompt.md`) bound to the
contract by a parity test. **CU2 — the loop:** on an unmatched intent and ONLY then, the
model reasons agentically and drafts STRUCTURED CLAIMS (a sentence plus the record ids it
believes support it); the draft never renders. **CU3 — claim-level verification:**
deterministic code, not a model, independently re-fetches each cited record and checks the
claim's assertions with the render validator's discipline → VERIFIED / INTERPRETIVE /
FAILED-and-cut. An assertion the records do not SPEAK to is unproven (labeled); one they
CONTRADICT is cut; a fabricated citation fails the claim; a correct-but-uncited claim is
never silently promoted; a quantifier is proven only when one call enumerated its set.
**CU4 — the surface:** claim blocks with per-claim provenance, the new `synthesis` register
(+ cockpit tokens in both themes), a rendered-by line naming the tier and the tool-call
count, and "prove it" as a new member of both parse vocabularies. **CU5 — the sweep**
(`tests/ai_exam/sweeps/2026-07-26-synthesis/`, 6 banks, **304 questions**, live): **90/93
graded expectations met**; validator 0, dark-evidence 0, dead-door 0, exception 0,
absent-entity 3 — identical to the baseline; **zero FAILED claims rendered**; parse 0
retries / 0 malformed (baseline 2 / 4). The tier itself: 32 answers, 100 claims — **42
verified, 55 interpretive, 3 failed-and-cut**, 8 honest couldn't-answers, 0 budget
exhaustions. **The seal, measured: 6 route moves across 212 shared questions, and the
120-question route fan moved nothing.** Both 4A.5a expect-misses resolved. **Riders:** (b)
the capability registry gains `min_chunk` (§5.3); (c) TOTAL conversational latency — parse
+ route median 1275ms / p90 2502ms, parse + synthesis median 9659ms / p90 16030ms; (d) the
rolling pre-route is RULED 4A.5c scope — the parse resolves subjects against the
Explainer's snapshot, window 0 only on a rolling run, so a beyond-horizon order would be
answered as ABSENT; it needs the rolling document's vocabulary in subject resolution first.
Full non-slow Python green (1386); slow AI ladders green (163); cockpit JS green (178).
**Telemetry aggregation, the Pareto and the promotion loop (R-AI5(5)/(7)) remain Session
4A.5c.** See the docs/04 2026-07-26 amendment.

**v2.44:** **AI-track Session 4A.5a — R-AI5 part 1: the LLM-first parse layer (the
classifier retires)** 2026-07-25 (R-AI5 verbatim + docs/04 amendment). Four founder exam
rounds proved a structural fact: every major conversational failure — polarity inversion,
hypothesis mis-routing, subject-binding outranking intent, a menu that could not match its
own items — was the deterministic keyword/precedence router failing to understand INTENT,
a natural-language problem solved with string matching. **R-AI5 ruled** (verbatim,
docs/04): parse first with a model against a CLOSED intent vocabulary; a matched intent
dispatches to contracted deterministic assembly, an unmatched one to labeled synthesis;
no classifier fallback and no silent path between the tiers; synthesis hardened by
claim-level verification; provenance visible per claim and assigned by verification, never
self-assessment; the promotion loop proposes, review disposes. **This session is part 1 —
the parse layer.** `Explainer.classify()` / `answer()` and `resolve_followup()`'s rewrite
rules are DELETED with their trigger tables; the ask path is now `parse -> dispatch ->
the unchanged route assembly -> the unchanged render + validator`. **CU1:** the
`ParsedQuestion` contract in `contracts/parse.py` (intent + typed subjects + polarity +
follow-up linkage + confidence + clarify), a parity test binding `Intent` to
`ROUTE_TAXONOMY`, and a one-call temperature-0 parser whose PROMPT is a governed,
versioned artifact; subject resolution stays deterministic and local (selection > last
answered > history, typed). **CU2:** dispatch honours every retired rule as a contract
field; two authored branches added (confirm-take, and advice's expedite-an-already-early
order). **CU3/CU4:** the founder's round-four session and 8 goal-pursuit scenario banks,
with a new `EXPECT` directive that machine-grades ROUTING only. **CU5:** the full
re-baseline sweep (274 questions, 5 banks, live) at
`tests/ai_exam/sweeps/2026-07-25-llm-parse/` — **61/63 graded expectations met; validator
0, dark-evidence 0, dead-door 0 (now live-checked), exception 0; absent-entity 3,
identical to the post-repair baseline**; parse retry rate 0.7%, clarify rate 3.8%, median
parse latency 1.01s. Full non-slow Python green (1329); slow `test_ai_voice` + `ai_exam`
green; cockpit JS green (178). **Parts 2 and 3 (synthesis + verification; telemetry +
promotion) are Sessions 4A.5b / 4A.5c.** See the docs/04 2026-07-25 R-AI5 ruling and
Session 4A.5a amendment.

**v2.43:** **Session CE1 — CLAUDE.md extraction (context-budget repair)** 2026-07-25
(docs/04 amendment). Claude Code reported `CLAUDE.md` over its 150k-char delivery limit
at **191,692 bytes**, of which the `## Current status` session changelog was **184,862
bytes (94%)** — a hand-maintained duplicate of docs/04 that pushed `## Working style`
to the far end of a file no longer delivered whole, so the sections that GOVERN how
sessions run were the ones most likely to be lost. The changelog was extracted; the
status section is now position + carried qualifications + carry-forwards only, **10,703
bytes** total. Nothing was cut unproven: 757 distinct facts across thirteen classes,
every numeric literal, all 46 session ids, and a sentence-level prose net were checked
against docs/04 + docs/07, and the **eight facts carried only in CLAUDE.md** (four
Phase-2-era commit hashes; four suite counts — 1278, 1211, 995, 795) were appended to
docs/04 verbatim BEFORE the cut. `## Hard rules` and `## Working style` byte-identical
(sha256 verified per section); no product/spec change. **Standing rule (W2):** session
close-outs go to docs/04 and docs/07, never into CLAUDE.md; CLAUDE.md is checked against
a **40k-char ceiling at every phase exit**. See the docs/04 2026-07-25 amendments.

**v2.42:** **AI-track Session 4A.3c — sweep repairs: the first triaged errand list**
2026-07-24 (docs/04 amendment). Executes the errand list the first exam sweep produced
(210 probes, live LLM, pinned glass_box); discovery already happened, this is repair.
Backend + a cockpit panel field + tests + docs; **no solver/model/contract/frontend
change; no golden moved.** **CU1 — the "but why?" defect:** a follow-up after a TYPED
entity question CLARIFIED because history is built from the SELECTION channel (no order
to bind); the panel now sends the prior answer's resolved subject as
`last_answered_subject`, and the interpreter resolves at priority **selection > last
answered > history > clarify** (the runner carries it identically — the harness inherits
the fix). Five enriched-context `test_ai_voice` fixtures refactored to realistic context
(a named standing discipline: context tests feed only what the shipped surface sends).
**CU2 — dark evidence (29 findings):** order-schedule / start-reason / machine-schedule
now light the bars of the placements they narrate (real assignment Decisions through the
existing `cited_refs` channel; prose unchanged — the routes stay authored/header-only).
**CU3 — the findings validator rate (11 fallbacks):** the LLM footnoted the finding-list
ordinal as a record; `findings` joins the authored-copy render path (verbatim), a
deterministic ~zero fallback rate — the remediation number-validator floor left intact.
**CU4 — the "order N" resolver:** "swap order 5 and order 4" / "order 15" resolve by
numeric inference against the pinned world's real ids (4A.3b KNOWN GAP flipped); guarded
so "show 5 late orders" stays a count. **CU5 — the loop closes:** the full bank re-ran
live to `tests/ai_exam/sweeps/2026-07-24-post-repair/`; the founder-precedent log seeded
with three OPEN judgment calls (lit-bars feel, invitation frequency, take frequency).
Full non-slow Python green; slow `test_ai_voice` + `ai_exam` green; cockpit JS green. See
the docs/04 2026-07-24 Session 4A.3c amendment.

**v2.41:** **AI-track Session 4A.3b — the exam harness: evaluation at machine speed,
judgment where it belongs** 2026-07-24 (R-AI4 + docs/04 amendment). The AI layer was the
differentiator with the SLOWEST evaluation loop — solver changes get machine-speed
verdicts, conversational changes waited for a founder listening session of ~a dozen
questions an evening; three founder rounds found every seam, all DISCOVERY failures the
corpus is structurally blind to. **R-AI4 ruled** (verbatim, docs/04): two axes with
different semantics (truth is a binary floor; conversation is the graded goal); roles
(sweeps discover, Claude triages, the founder is final arbiter); fluency not engagement
(invitations complete the thought, silence is a register); audits run against the pinned
document, never a re-solve. Backend + tests + docs; **no solver/model/contract/frontend
change; no golden moved** (the one behavior change is CU4, additive invitation copy).
**CU1 — the runner** (`python -m mre.ai_exam`): fires a question SCRIPT through the REAL
ask path (interpreter/explainer/renderer/validator, LLM LIVE) against a pinned run, state
persisting across the file (SELECT/RESET directives); plain-ASCII transcript + a
mechanical findings sidecar; a `target-unloadable` guard fires loud on a wiped run rather
than emit garbage. **CU2 — the banks** (`tests/ai_exam/banks/`): founder rounds 1–3
verbatim (with typos) + paraphrase fans + trap probes — **210 probes, 182 sweep**.
**CU3 — the rubric** (`RUBRIC.md`): truth-floor checks + five conversation dimensions +
four output buckets (DEFECTS / CONVERSATION FAILURES / JUDGMENT CALLS / EXEMPLARS) + the
built mechanical pre-triage. **CU4 — invitation generalization** (R-AI4(3)): coaching +
gap-between join the invited routes, contextually composed, each opening a live route (a
fast real-doors reverse-guard proves it). **CU5 — the first sweep** ran live (96 calls,
210 questions) against a pinned glass_box solve, transcript + sidecar committed under
`tests/ai_exam/sweeps/2026-07-24/`; discovery only — fixed nothing. Sidecar counts:
dark-evidence 29, validator 11, absent-entity 3 (all legitimate seeds). **CU6 riders:**
the parallel-load screenshot-flake class named as standing debt; the corpus gained the
solve-#5 natural-language swap phrasings (pinned as a known gap — "order 5" does not yet
resolve to ORD-05). Runner tests + real-doors + CU4 specimens green; non-slow Python
green; `test_ai_voice` slow green. See the docs/04 2026-07-24 R-AI4 + Session 4A.3b
amendments.

**v2.40:** **AI-track Session 4A.3 — the action bridge: the conversation reaches the
board** 2026-07-24 (docs/04 amendment + the CU7a resolving amendment). The founder's
round-three listening session (solve #5 pinned) found the register ladder works where
wired but the conversation could not REACH the board. Backend + a cockpit tooltip + the
selection channel; no solver/model/contract change, no golden moved. **Part 0 — CU7a
overturned:** the ORD-000019 → ORD-000015 blocked-by claim is CONFIRMED TRUE on the live
board; the 4A.3-pre "fabrication" verdict was an artifact of auditing against a re-solve
of a DIFFERENT world (CP-SAT non-reproducibility biting the audit). `_blocked_by`
exonerated. STANDING PROTOCOL: conversational-claim audits run against the pinned run's
persisted document, never a re-solve. **CU1 — the swap/move bridge (flagship):** "why
not just swap X and Y" now routes to `swap-move` and answers the R-AI3 ladder —
TESTIMONY (both orders' placements + slack/lateness) + a grounded TAKE (who can afford
the slot) + the BRIDGE to the real board gesture the two-beat sandbox prices; the panel
proposes, the human drags (M10 has no write path). **CU2 — the absence pair (promoted
from debt):** `gap-between` names the gap's cause on the shared machine (occupancy /
closure / off-shift / upstream / else honestly unexplained, never vouched);
`machine-idle` redirects a used machine without naming the wrong noun, scopes an idle
one honestly. **CU3 — selection reaches the interpreter:** a demonstrative deictic
("this order") resolves SELECTION-FIRST before the router short-circuit, the interpreted
line naming the source. **CU4 — coaching fixes:** bare concept names + an
enable/use/explain verb reach coaching; a NEW overtime concept (§5.6/§5.9); a
menu-selection follow-up ("what about wip") coaches the concept, not an entity. **CU5 —
riders:** the job-bar tooltip gains span + lateness/slack. Non-slow Python 1255 passed,
0 failed (+6 fast); slow `test_ai_voice` green with the new specimens; cockpit planner
tooltip spec green both themes. See the docs/04 2026-07-24 Session 4A.3 + CU7a resolving
amendments.

**v2.39:** **AI-track Session 4A.3-pre — R-AI3 (the register ladder): restore
judgment, add invitation, fix the round-two exam findings** 2026-07-24 (docs/04
amendment). The founder's round-two listening session ratified R-AI3 — every answer
starts with the facts; testimony is the base, a labeled "My take:" earns its place
above it, an invitation may end it, disagreement is met with warm evidence not
capitulation. Backend-only; no solver/model/contract/frontend changes; no golden
moved. **CU1 — judgment restored + archaeology named:** the "My take:" rode the
TEMPLATE floor only (a 4A.2d named debt), so the LLM default paraphrased it away; it
is now APPENDED (authored) after the LLM testimony so the model cannot drop it, on
why-late (flagship) + the advice route's scoping answer, ABSENT on lookups (a
negative test), with a standing LLM-path regression guard. **CU2 — invitations:** one
authored, question-phrased offer of a SUPPORTED route on late-orders / why-late /
data-problems; absent on lookups; the ladder stacks testimony → take → invitation.
**CU3 — start-reason polarity:** "why so early / not due until {date}" now answers the
R-SC3 floor (finishing early is free; cost-equal work placed as early as it can,
banking slack) + the concrete lower bound as supporting testimony; "why can't it start
SOONER" keeps the lower-bound chain. **CU4 — coaching retrieval:** a new `coaching`
route retrieves from a NEW authored capability registry (`capabilities.py`,
`dict[concept → CapabilityNote]` with a docs/06 § citation borrowed from the gate's
`RULE_REGISTRY`); anchor "i want orders to span downtime, how" → splittable=true +
min_chunk, §5.3; the "No calendar closures found for all resources" nonsense fixed to
"No downtime is declared for any resource." NAMED DEBT: docs/05 is prose-locked, so
the fuller constraint-coaching surface is not built. **CU5 — hypothesis-content
guard:** an intervention STATEMENT ("maybe if splitting were allowed fewer orders
would be late") routes to coaching/advice by content shape, never the status recital.
**CU6 — sycophancy guard:** a contested fact ("isn't ORD-05 on time?") is met with warm
evidence + an offer to walk the chain, never capitulation, never hardening; the
balance case (an accurate correction) yields. **CU7a:** the founder's ORD-000019 →
ORD-000015 blocked-by claim mechanically verified against a deterministic busy_board
re-solve — FALSE (fabrication, filed severe): the shared-machine kernel is real but
the adjacency + 14:23 timestamp are stitched from unrelated facts (the two ops are ~4
days apart; 14:23 belongs to a third order on another machine); blocked-by NOT touched
this session. **CU7b named debt:** aggregate-cause coaching + the bare-elliptical "why
so many" against the context slice. Non-slow Python 1249 passed, 0 failed; slow
`test_ai_voice` 78 passed (+15 R-AI3 specimens); `test_glass_box` + `test_ask_chain_api`
green. See the docs/04 2026-07-24 R-AI3 ruling + Session 4A.3-pre amendment.

**v2.38:** **Session 4B.4 — R-SC3 extended to ALL solve paths (the monolithic
floor) + the founder's conversational fixes** 2026-07-23 (docs/04 amendment). The
founder's live listening session found the R-SC3 floor (earlier starts among
cost-optimal placements) was implemented on the ROLLING path only — the monolithic
schedule of record still parked cost-equal work arbitrarily (ORD-000038 sat behind a
free earlier slot at $0.00 delta). **CU1:** a shared `solver_builder.solve_two_stage`
lifts the exact two-stage shape into the monolithic path (`__main__`): stage 1
minimizes cost (+ the declared `earliness_value` term), recorded so the M6
solve_complete objective stays the COST objective; stage 2 caps that optimum and
re-minimizes the sum of free-op starts (warm-started, deterministic budget). One
floor, unscoped. Per-site audit: the schedule of record gets stage 2; the re-solves
(sandbox beat two, scenario, planner_edit) are exempt (they warm-start from the
two-stage incumbent, inheriting the floor, and diff against it); solution_pool exempt
(diversity is its secondary objective); forced_alternatives + beat one exempt
(pricing / feasibility probes). `sample_data_schedule.csv` regenerated DELIBERATELY —
cost ledger IDENTICAL pre/post (24769.00 / 19429 / 4500 / 840, verified), only
placements moved net-earlier; rolling goldens BYTE-IDENTICAL. **CU2:** an `advice`
route scopes recommendation questions honestly (what the product can do + intervention
recommendation is not yet supported), never the late-orders status recital; the
clarify/near-miss leads no longer echo a frustrated sentence verbatim. **CU3:** three
routes added before the bare-"schedule" branch — `solve-time` + `machine-count` (cheap
document/evidence reads) + `maintenance` (shape-recognized, honest not-yet) — killing
the "I don't see any scheduled operations" category-error insult. **CU4:** typed
anaphora ("that machine" binds only to a machine, then recency; no type match ->
clarify) + repair-on-correction (re-answer the prior question with the corrected
referent, never a menu-dump). **CU5:** list-expansion — "list them"/"the numbers"
re-fires the last route in list form. **CU6:** (a) order-schedule states earliness
once, per-row only when rows differ; (b) "Customer: not specified" coaches the
customers doorway. **Named debt (not built):** the absence-explaining route pair
("why the gap X-Y" / "why is machine M unused"), the calendar-awareness cluster, and
the action bridge (4A.3 — this session is standing evidence it is next). Non-slow
Python 1243 passed, 0 failed; slow ladders green (`test_ai_voice` 63, glass_box +
ask_chain 34, all re-solve exemption ladders). See the docs/04 2026-07-23 Session
4B.4 amendment.

**v2.37:** **Session 4B.3c — rolling parity: sliced runs become first-class
citizens** 2026-07-23 (docs/04 amendment). Retires the three named debts that were
one fact — a rolling run was second-class in persistence and the API. **CU1:**
`build_rolling_view(persist=True)` writes the window-0 solve as a FIRST-CLASS RUN —
Assignment/ServiceOutcome/Schedule into the canonical snapshot (`is_scenario=False`,
RECONSTRUCTED basis) + assignment Decisions + M5 horizon + M6 solve_complete
evidence — so the sandbox and Explainer read it exactly as a monolithic run;
persistence OBSERVES, never influences (persist digest == no-persist digest, proven;
the rolling determinism golden survives); the completeness invariant is now counted
against the PERSISTED document. **CU2:** the rolling document carries the Tier-0
`interaction` payload for its ACTIVE WINDOW (committed bars carry no interaction op →
non-targets by construction). Schedule **contract 1.7 → 1.8** (additive; the field
existed since 1.2). **CU3:** `feasibility_ghost`/`sandbox_pin_resolve` gain
`restrict_op_ids` so the two-beat endpoints re-solve the WINDOW against the persisted
incumbent; the API's `_rolling_gesture_context` hands them the window op set + the
frozen front as standing pins. All 4B.3b invariants re-proven on the rolling
substrate — `no_committed_work_changes` now LOAD-BEARING; the FORCED infeasible
contradiction demonstrated by gesturing an active op at a committed slot (beat one
relaxes → feasible; beat two holds → infeasible, naming the commitment). **CU4:** the
three sliced-world routes registered in `ROUTE_TAXONOMY` and answered from the
document via `rolling_questions` in a `/ask` pre-route (logged to the ledger),
hedging honestly; everything else falls through to the Explainer over the persisted
snapshot — **"ask why" is a real grounded answer now (R-AI1 rolling-explainer debt
RETIRED)**; the cockpit ask-why button auto-bridges to the ask panel on a rolling
board. **CU5:** (a) the card's affected-orders column label reads lateness/tardiness
impact, never cost; (b) named debt — per-order production-dollar attribution (a
ledger change). Non-slow Python **1239 passed, 0 failed**; new slow: rolling two-beat
**11** + rolling API **3**; both goldens byte-identical; cockpit JS **168 → 176**
(+8 rolling two-beat, both themes).

**v2.36:** **Session 4B.3b — the two-beat sandbox (R-T2 implemented)** 2026-07-23
(docs/04 amendment). Makes the Tier-2 sandbox + forced-alternative gestures a
TWO-BEAT interaction per R-T2. No solver/model/schedule-document changes (rides
module dataclasses + new API endpoints; monolithic AND rolling goldens
byte-identical). **CU1 beat one — the feasibility ghost:** `feasibility_ghost()` +
`POST /sandbox/feasibility` — a FIRST-FEASIBLE solve (small deterministic budget,
CP-SAT `stop_after_first_solution`) returning feasibility + placement + a
correlation id, carrying NO money BY CONSTRUCTION (the `FeasibilityGhost` type has
no cost field; a contract test asserts field ABSENCE). It RELAXES the committed work
(so beat two can contradict it) and MINTS NOTHING (tested). **CU2 beat two — the
LAYERED priced card:** `sandbox_pin_resolve` enriched — an always-visible layer
(signed total, feasible/rejected, moved-op placement, top-N affected orders with
per-Demand tardiness/lateness deltas, lateness introduced/recovered, the dominant
driver hedged, "no committed work changes" asserted) + a detail layer (cost
decomposition by ledger line summing EXACTLY to the verdict with an explicit "other"
remainder — rollup_of-tested; + operational consequences). Ghost→card supersedes
through a perceivable transition (a feel token). **CU3 the contradiction (R-T2(4)),
shown not reconciled:** the INFEASIBLE case is FORCED end-to-end via a standing-pin
conflict (beat one relaxes it → feasible; beat two holds it → infeasible); the MOVED
case is unit-proven + frontend-exercised and NAMED (a pinned op cannot relocate
between exact-pin beats — what diverges is the consequence set). **CU4** the
forced-alternative gesture (a cross-machine pin) runs the identical two-beat path.
**"Ask why"** ships but routes to a graceful NAMED-DEBT response — the SAME R-AI1
rolling-explainer connector debt (now with two blocked consumers; docs/04 entry
extended, not double-booked). **Rolling active-window wiring** is NAMED debt (the
rolling snapshot persists no incumbent + no interaction payload — connector-era
work); the two-beat is delivered + proven on real monolithic solves + the gesture
fixtures, rolling-ready (committed work held via standing pins). Non-slow Python
**1239 passed** (+12); slow two-beat 15 (no skips); cockpit JS **156 → 168**
(+12, both themes). Goldens byte-identical.

**v2.35:** **Repo relocation + R-T2 + Session 4B.3a — the cockpit renders the
sliced world (read-only)** 2026-07-23 (docs/04 amendment). Repo moved to
`C:\dev\mre` (OneDrive path retired); relocation confirmed — `git fsck` clean, 1219
passed (one editable-install `.pth` still pointing at OneDrive was the sole defect,
repointed). **R-T2 transcribed** (two-beat Tier-2 contract: beat one shows no
money and renders in the R-M1 ghost class; beat two prices + supersedes visibly; a
contradiction is shown via rejection semantics; beat-one mints no edits —
IMPLEMENTED in 4B.3b). **4B.3a** makes the cockpit render pilot_scale's rolling
output READ-ONLY. **CU1** contract **1.6 → 1.7 (additive)**: `AssignmentBlock.commitment_state`
(committed | active_window), `ScheduleDocument.rolling` (window metadata +
beyond-horizon list), and the **COMPLETENESS INVARIANT** (every schedulable demand
appears exactly once — committed/active/beyond — enforced by the assembler,
COUNTED by a test). `build_rolling_view` (solve window 0) + `assemble_rolling_document`
+ a `SolveRequest.sliced` API path register a rolling document like any run.
Monolithic goldens byte-identical. **CU2** board renders it: committed bars LOCKED
(static, no gesture), a labeled frozen-front boundary marker, and a docked
beyond-horizon TRAY (empty state shows zero, never hidden) — real fixture from a
real solve; cockpit JS 146 → 156, both themes. **CU3** `rolling_questions.py` answers
the three rolling questions (beyond / why-not-yet / frozen), planner-voiced +
hedged; the interpreter/ledger/taxonomy wiring is a NAMED R-AI1 DEBT (rolling runs
must persist a snapshot the Explainer reads first). **CU4** (a) `anthropic` added as
a dev extra; (b) the audit corpus gains the attribution-limitation specimen — a
capacity-forced dearer placement attributed to EARLINESS_PREFERENCE now HEDGES
(names the preference AND that capacity may bind), joining the zero-confident-wrong
corpus. Full non-slow suite green (1227); slow rolling + AI ladders green.

**v2.34:** **Session 4B.2d — R-SC3: earliness as tiebreak + declared coefficient**
2026-07-22 (docs/04 amendment). Supersedes the 4B.2 hidden weight-1/min earliness
incentive (4B.2c proved it spent an undeclared +$74.30). **R-SC3:** earliness is a
ZERO-COST lexicographic tiebreak (the FLOOR: among cost-optimal schedules, prefer
earlier starts), and PAID earliness is a declared `CostModel.earliness_value`
($/min); no internal undeclared weight may move placement; idle-minutes are
conserved and belong in Metrics, never the objective. **CU1** two-stage solve
(stage 1 = cost + priced earliness; stage 2 = cap cost, minimize op-start
earliness) replaces the incentive. **CU2** full IDS doorway: §5.9 column + rule
#35 `ids.earliness_value_sane` (registry 34→35) + adapter provenance
(observed/defaulted) + catalog note + pilot_scale demo value 0.05 $/min. **CU3**
driver `EARLINESS_PREFERENCE` (12→13), reachable via the existing why-on-machine
route. **CU4** 4B.2c's xfail FLIPPED to two hard passes on an 8-order monolith: (a)
coeff 0 floor == plain cost-only to the cent ($5,719.83, epsilon 0); (b) coeff 0.05
= +$33.60, start-sum gained 7,097 min, bound holds, 2 placements cite the driver.
**CU5** per-resource manned-idle Metric. **CU6** window curve re-run (both
coefficients) + golden regenerated DELIBERATELY ($14,708.38 → $14,904.05,
production-only). Full non-slow suite green (1219); slow rolling ladder green, no
xfails.

**v2.33:** **Session 4B.2c — measurement-integrity errands (post-audit)**
2026-07-22 (docs/04 amendment). A read-only audit of 4B.2 produced an errand
list; this session executes it — scoped fixes/tests/docs only, NO mechanism
redesign, no window-curve re-run. **CU1 (load-bearing):** the earliness incentive
(`rolling_horizon.py`) is a GLOBAL weight-1/min ASAP pull (its "fills the frozen
front" comment overclaimed — corrected). Counterfactual (incentive on vs off,
deterministic): its reach is bounded **IN COST** — total +$74.30 (+0.290%, within
a 1% epsilon), no priced line worsens (extractor prices production+setup+tardiness
only, so an ASAP pull has no JIT/inventory downside) → **PASS**; but it is **not
placement-neutral** (it relocates a 7-op job to a dearer-but-earlier machine,
paying that $74.30) → that assertion is recorded as **xfail** with the numbers,
not tuned away. **CU2:** the committed 4B.2 latency was measured on a **0-op
window** (void); RE-MEASURED on the MOST-LOADED 7-day window (44 free ops): build
0.028s, solve-to-first-feasible 0.275s, solve-to-budget 4.95s (FEASIBLE), a
forced-alternative sandbox re-solve 3.826s — a proven verdict/priced ghost is
**seconds, not sub-second**; all figures are DEMO density (60/141/15), pilot
volume (174 workcenters) UNMEASURED. **CU3:** a rolling-determinism GOLDEN
(`tools/rolling_golden.py` + committed `rolling_pilot_golden.json`, digest
`b595c724…`) — two subprocess rolls agree with each other and the golden (detects
DRIFT, not just intra-run). **CU4:** mechanism tests via a new `window_observer`
hook — frozen-front commit split (exactly the inside-zone ops commit) + absolute
origin (committed ops never re-placed, no pin RECORDS minted). **CU5:**
PREDICTIONS.md GRADED — **3 CORRECT / 3 PARTIAL / 1 WRONG / 2 NOT-EVALUABLE**
(WRONG: ASM-01 not the bottleneck at this light load; a data fact surfaced —
pilot priority rides `customer_weight`, not `commitment_class`). **CU7:**
`deploy/ci_local.ps1` reproduces the ci.yml image-as-shipped gate locally. Named
debt: per-component gravity ablation (the counterfactual proved the BUNDLE;
setup-family affinity is the priced-air candidate). R-SC1 wording corrected (the
gate bypass exited the TEST path; live raw paths remain, Phase-4 debt). Two
rolling-runner additions are test seams (default-on incentive toggle + observer),
production behavior unchanged. See the docs/04 2026-07-22 Session 4B.2c amendment.

**v2.32:** **Session 2.4b (partial) — the FIRST real container build; in-container
CI CONFIRMED** 2026-07-21 (docs/04 amendment). Docker became available, so the 2.4
CU1 carry-forward ran: build the image per the Dockerfile and run the fast suite
INSIDE the built container (green CI on the image AS SHIPPED, not the checkout).
The never-built image found **seven** fixes across the four predicted classes —
(1) **lockfile drift**: `numpy==2.5.1` needs Python ≥3.12 but the image ships
3.11-slim → repinned `numpy==2.4.6` (the lock had been regenerated on a 3.14 host;
a base bump was rejected — it would break the pinned ortools cp311 wheel); (2)
**missing runtime dep**: `mre.catalog` imports `yaml` (reached by the certificate's
remediation register) but PyYAML was in neither lock → added `pyyaml==6.0.3` (the
shipped image couldn't import the register until this); (3) **missing test inputs**:
`docs/` was `.dockerignore`-excluded and `datasets/` never COPYd, but spec-derived
tests read `docs/06` and the Glass Box gate/sabotage tests read `datasets/glass_box`
→ un-ignored docs + `COPY docs`/`COPY datasets` into the **test** stage only
(runtime stays lean); (4) **a shipped-code bug the mock hid** (mocked≠real, cf.
4A.1b): a dead unguarded `import anthropic` in `LLMRenderer._call_llm`/`_llm_judgment`
made an injected-client render raise `ModuleNotFoundError` wherever the SDK is
absent → removed (the guarded construction import stays); (5) **latent fragility**:
`mre.demo`'s `__file__`-relative sample-data path resolved into the venv when
installed → robust `_sample_data_dir` (env / checkout / cwd); (6) **layout
assumptions**: three architectural guards (`declared_but_unread`, explainer
NoWritePath, solver_builder SixInputRule) read `src/` source the image omits →
resolve via the imported package's `__file__` (the source that actually ships).
**Verified:** runtime image builds as shipped; **1200 passed / 23 skipped / 0
failed inside the built test image**; compose stack up (API + `/data` ext4 volume,
non-root `mre`); **`/health` from INSIDE the container**; **`deploy/smoke.py`
against the CONTAINERIZED API** → ACCEPTED/C1, 60 assignments, 2.31 s. **The 2.4b
qualification PARTIALLY retires — in-container CI CONFIRMED; live `az deployment` +
cloud smoke remain PARKED on the Azure trigger** (no live subscription). See the
docs/04 2026-07-21 Session 2.4b amendment. Lesson: a never-built image always has
something; the stale-install false-green lesson applies to images — make the
artifact match reality (pin the shipped Python, ship what you import, copy what
tests read) and point layout-coupled code/tests at the installed package, not the
checkout.

**v2.31:** **Session 4B.2 — the pilot_scale plant + the measurements that decide
the slicing architecture** 2026-07-21 (docs/04 R-SC1/R-SC2 rulings + amendment).
**R-SC1** — the historical ticketing extract is INTELLIGENCE, not a fixture:
demoted to a PROFILE source (`tools/extract_pilot_profile.py` →
`datasets/pilot_scale/pilot_profile.json`; volumes/order-size/family-cardinality/
machine-count/lead-time SHAPE only), plant physics AUTHORED in a synthetic
pilot_scale plant; the raw_data gate bypass exits the test path (gauntlet tests
removed). **R-SC2** — SLICING IS A ROLLING HORIZON with a frozen zone + gravity
admission (must-start-by / weighted-criticality / setup-family affinity); window
length chosen by MEASUREMENT.

**The slicing plan of record.** The blessed operational mode is the rolling
horizon (`src/mre/modules/rolling_horizon.py`): the spine runs once
(`prepare_plant`), then per window admit demands by the time window PLUS the three
gravity pulls, build a model over the admitted-and-uncommitted operations
(earliness-pulled, floored at the window start), solve deterministically, and
COMMIT the frozen front (every operation starting inside it); committed work is in
the past for every future window, so it constrains nothing and needs no pin. The
**measured window curve** (pilot_scale, 60 orders / 141 ops / 15 machines,
deterministic): cost + lateness fall from a myopic 2–4-day window (~$46k, 7–10
late) to a **7-day window ($37.7k, 1 late)** and then plateau — the **KNEE is 7
days ≈ the profile's 7.5-day median lead time**. Deployment rule: **size the
window to the plant's lead time, and find it by the knee, don't guess.** Frozen
depth is a separate declared parameter (2 days here). The gravity counterfactual
proves look-ahead: a monster job whose must-start precedes its due-window finishes
on time WITH admission and goes 6,781 tardiness-minutes late WITHOUT it. Density
(9.4 ops/machine, 141 board bars) + per-window interaction cost (sub-second)
size the cockpit **4B.3 retrofit**, designed FROM these numbers (the cockpit is
NOT retrofitted this session — pilot_scale has no monolithic solve to render).
Far-horizon look-ahead pricing, chunk-level frozen commit for splittable ops
longer than the frozen zone, and RawAdapter retirement are named/parked. Density
+ curve + gravity + latency in the docs/04 measurement table;
`tests/test_rolling_horizon.py`. See the docs/04 2026-07-21 R-SC1/R-SC2 + Session
4B.2 amendments.

**v2.30:** **AI-track Session 4A.2d — R-AI2 (conversational-by-default) + the
4A.2c correctness specimens** 2026-07-20 (docs/04 R-AI2 ruling + amendment).
Correctness and voice land in ONE session so neither ships without the other.
**R-AI2 ruled** (verbatim, docs/04): the voice is conversational; the template is
a fail-closed FLOOR written as sentences, not a register; judgment ("My take:") is
a labeled first-class guest, never blended into testimony; the transcript
convention (=== headers, meta-footers in the planner's view) dies; guards gate
CONTENT, never voice. **Part 2 (correctness):** **CU1** — a deictic (this/that/it)
resolves against the live selection on EVERY route; a machine ref no longer
short-circuits resolution when a pronoun is also present ("why is this on CUT-01"),
and no subject → CLARIFY — the literal token never reaches a route as an entity.
**CU2** — "Nothing scheduled for all" (a scope placeholder) is unrepresentable; an
empty listing with no filter reads as an honest sentence, and the placeholder only
ever names a REAL entity. **CU3** — a direct timing question leads with the asked
quantity ("ORD-13 completes … — 8.5 day(s) early"), the seq= table supplementing.
**Part 3 (voice pass):** the `=== q ===` transcript header removed (the answer
opens with the answer; the `[rendered by]` footer kept as delivery metadata, the
cockpit register chip being the R-AI2(d) indicator — footer-line hiding in the
cockpit view is a named 4A.3 follow-up); the schedule listing re-rendered as a
colleague sentence with the rows as supplement; why-on-machine composed as a
sentence ("{order} is on {machine} because {plain cause}"); a LABELED judgment
offered on a late order blocked by earlier work ("My take: pull {blocker}'s start
earlier, or accept the N minutes"). Backend-only (explainer + interpreter +
renderers + planner_language + corpus + docs); no solver/model/contract/frontend
changes. Named: the "My take:" offer rides the template floor (the LLM testimony
path keeps its no-opinion rules — a dedicated judgment turn is a follow-up); the
cockpit footer-line hiding is 4A.3. Non-slow Python **1209 passed**, 0 failed; the
slow AI-voice corpus green (+5 specimens, re-graded on facts-correct AND
question-answered AND voice-conversational). See the docs/04 2026-07-20 R-AI2 +
Session 4A.2d amendments.

**v2.29:** **Session 4A.2b — the listening-session findings** 2026-07-20 (docs/04
amendment). Daryn's first live conversation surfaced four delivery gaps between
4A.2's claims and its behavior, plus frontier items; every specimen is in the
question ledger and now in the standing corpus. **CU1 — the blocked-by chain names
the culprit:** the deterministic why-late sentence already named the blocking
order + release time ("CUT-01 was held by ORD-13 until Mon 18:50"); live, the LLM
path compressed it back to the driver phrase ("busy with other work"), so the
blocker (order, machine, release time, priority) is now PINNED into the LLM's
pre-computed facts — quotable, never compressible. **CU2 — cross-register
coherence:** testimony counted the advisory validator finding ("1 problem") while
remediation/triage — reasoning over only gate-certificate findings — said
"nothing"; the two registers now reason over the SAME finding set and render an
advisory ("N advisory finding(s), no action required — …") rather than "clean"
opposite a reported problem. **CU3 — formatting leakage:** markdown + backtick
stripping at ONE delivery seam (`planner_language.strip_formatting`, applied in
both renderers' public entry points), not per-route. **CU4 — named input on every
finding path:** a defaulted-input finding names the INPUT in planner words ("the
customer priority weight", never the raw column), the affected orders (capped
sample + count), and a fix (authored `INPUT_FIX`, or a code-level catalog
fallback). **CU5 — rewrite-confidence guard:** a bare "but why?" resolves to the
last subject's cause-chain; a SET-referring follow-up ("10 of those") and a
verification of a prior claim ("is that correct") CLARIFY instead of being mangled
into a single-order question. **CU6 — fuzzy entity tolerance:** near-miss ids
(ord-o5 / ORD-5 / ord 05) resolve to the canonical order with a visible assumption
("assuming ORD-05"); an id of the dataset's shape resolving to nothing still gets
the honest "isn't in this schedule". Backend-only (planner_language + explainer +
interpreter + renderers + remediation/triage + ask_fallback_copy + corpus + docs);
no solver/model/contract/frontend changes. Named/frontier (not addressed): the
board's spatial "show me" (4A.3); UTC-vs-local clock labeling; "move it to a
different machine" bridging to the edit gesture rather than refusing. Non-slow
Python **1209 passed** (was 1202; +7 fast), 0 failed. See the docs/04 2026-07-20
Session 4A.2b amendment.

**v2.28:** **Session 4A.2 — the voice (the AI/CERTIFICATE floor + the wow layer)**
2026-07-20 (docs/04 amendment). The founder's Glass Box close: *the core is
trustworthy; the voice is inadequate to it — the AI is the differentiator and
must be fantastic, not merely good.* This session takes the AI/CERTIFICATE half of
the close, driven by the ~14-finding failure taxonomy whose specimens live
verbatim in the question ledger. Backend-only. **Split honestly:** ships Part 1
(the floor, CU1–CU6) + CU7 (morning briefing) + CU9 (proactive excluded) + CU10
(the measurement); **CU8 (spatial "show me")** is NAMED and deferred to **4A.3**.
New authored `planner_language.py` (12 driver + 18 finding codes → plain cause,
stage names, jargon strip, the four-part finding-sentence composer with
coalescence). **CU1 (keystone):** the relevance guard — a route fires only when
the SHAPE matches; a named-but-unresolvable order gets the excluded/unknown
answer, never a global "Yes" (evidence-derived excluded-labels + a dataset-learned
order shape, no id-shape assumption); the answer-the-noun catch-all and the
`"diff" in "different"` bug are gone. **CU2:** findings render (subject, offending
value, plain cause, catalog fix), coalesced — replacing the subject-blind "Total
findings" header. **CU3:** drill-down opens the full finding behind a citation.
**CU4:** the blocked-by chain reads the solved occupancy ("CUT-01 held by ORD-13
until Mon 18:50"); driver codes decompressed to plain cause. **CU5:** the missing
route families (attribute lookup, inventory, integrity/double-booking check,
release/start reasoning). **CU6:** the register-tag seam fixed (chip==envelope via
one `REGISTER_BY_SUBJECT`; enumerating findings is testimony), layer coalescence,
module-id → stage-name, jargon strip, citation-breadth cap. **CU7:** the morning
briefing as a triage (fires by lateness × priority, common cause, the one DQ item).
**CU9:** exclusions volunteered in relevant answers. **CU10:** `tests/
test_ai_voice.py` — the audit corpus as standing acceptance, every specimen
re-run against a real Glass Box solve, **zero confident-wrong** asserted. Non-slow
Python **1202 passed** (+12), 0 failed. See the docs/04 2026-07-20 Session 4A.2
amendment. **Carried:** CU8 → 4A.3; the presentation findings (UTC-vs-local clock
labeling; move-it could bridge to the board-edit gesture) remain named.

**v2.27:** **Session 4.5 — the unguarded-edge family + severity semantics**
2026-07-20 (docs/04 amendment). Four findings from Daryn's live Glass Box audit —
three architectural misses and one disease. **CU3 (the disease):** severity meant
nothing — a finding could claim `error` while proceeding. `contracts.records.Finding`
now enforces error/blocker ⇒ acting disposition; the M0 gate's finding severity
derives from the DISPOSITION (`finding_severity`), grade still from the outcome, so
a degraded-but-proceeded rule is honestly a WARNING (the specimen:
VALUE_OUT_OF_RANGE/proceed). **CU2:** new gate **rule #34
`ids.order_quantities_are_positive`** (registry now 34) — a quantity ≤ 0 degrades
to CONDITIONAL and the order is excluded. **CU1:** a ServiceOutcome requires ≥1
real operation — the extractor refuses a vacuous fulfillment; the adapter takes
the orphan-demand path for an unroutable order (zero-active route), EXCLUDED not
EARLY. **CU5:** `_td_to_minutes` raises on a negative duration (the -180→1min
laundering closed at the seam). **CU4:** an `excluded-orders` certificate route
enumerates every exclusion from all layers, so the report card is never blinder
than dq_report.md. Non-slow Python 1190 passed (+18); frontend untouched. docs/02
§4.3 severity table + docs/06 v0.6 updated same commit. See the docs/04
2026-07-20 Session 4.5 amendment. **Audit carry-forwards (founder's close, NOT
addressed this session):** the founder's verdict is *"the core is trustworthy — I
tried to catch it lying and could not; the voice is inadequate to it. The AI is
the differentiator and must be fantastic, not merely good."* Named work ahead: (a)
**the AI/CERTIFICATE voice** — a saturated ~14-finding failure taxonomy
(answer-the-noun / answer-the-wrong-noun; subject-blind finding renders; no
drill-down; no coalescence; register-tag seam; layer/driver jargon; markdown leak;
citation-breadth absurdity; dq_report.md unreachable from the conversation — the
last only *partially* reached by 4.5 CU4) → the AI track / 4A.2, the
differentiator; (b) **presentation** — unlabeled UTC-vs-local clocks disagreeing
across surfaces, and causal narration that stops at driver codes rather than
plain cause.

**v2.26:** **Session 4.4 — schedule freshness done right (the sixth stale-tab
incident)** 2026-07-19 (docs/04 amendment). The behavior contract: **the cockpit must
never leave the user unknowingly on anything but the newest relevant schedule.** 4.3's
newer-schedule detection was real but half-scoped (same submission only), and the
sixth incident proved that blind to the RESUBMIT workflow — a data fix in Excel →
re-submit mints a NEW submission id → the newer solve was never offered. **CU1 —
scope fix:** `findNewerSchedule` compares against the newest LIVE schedule across the
whole DATA ROOT, not the same submission ("relevant" for single-tenant/dev = the
root); strictly newer by `created_at`, a same-instant tie is NOT newer (unrelated live
boards never cross-follow); multi-tenant scoping NAMED as a future concern, not
pre-built. **CU2 — auto-follow (the real fix):** with NO uncommitted user state, a
newer schedule appearing while viewing auto-follows (reload onto the new version + a
brief R-M1-legible toast "Switched to the new schedule · View previous", one click
back via a `sessionStorage` handoff). With uncommitted state — a drag mid-flight, an
open card, or a pinned conversation (`panel.hasUserState()`: live selection / built-up
Q&A / ask in flight) — NEVER auto-switch; fall back to the 4.3 banner and let the
planner decide. Re-checks on window focus + tab re-show + a 30s backstop (focus is the
return-from-Excel signal). **CU3 — identity visible:** `/meta` carries a `generation`
counter (1-based monotonic "solve #N" over the root's non-scenario schedules) +
`created_at`; the strip shows "solve #3 · 09:41", hex in the title — two
visually-similar boards distinguishable at a glance. Harness: `POST
/__test__/add-schedule` injects a newer schedule; the three CU2 flows + CU3 + a
strengthened CU6 (no spurious follow on a normal boot) driven end to end. **Cockpit JS
146** (was 137); **non-slow Python 1172** (additive `get_schedule_meta`). See the
docs/04 2026-07-19 Session 4.4 amendment.

**v2.25:** **Session 4.3 — Glass Box audit riders + R-DP9 (the no-op drop)**
2026-07-18 (docs/04 amendment). Eight small findings from Daryn's live audit,
batched; no solver/model/contract changes. **R-DP9 ruled:** a drop within snap
tolerance of the op's INCUMBENT placement is a NO-OP — settle home with an "already
here" cue, commit nothing (no sandbox, no zero-delta Decision, no standing pin); the
mirror of R-DP8 (a real commitment must survive every solve; a non-commitment must
never become one). **CU0:** verified `dev_api.ps1` loads a gitignored `.env.local`
end to end (a key reaches the LLM renderer with no terminal typing); added a
committed `.env.local.example` + README dev section. **CU1:** the ledger/legend
collision (SECOND occlusion incident) made STRUCTURAL — a `.board-chrome` row holds
the legend (left) + zoom/ledger (right); the ledger is a thin tab whose body drops
UPWARD over board space, `wrap-reverse` lifts the right cluster above the legend when
narrow; bounding-box non-intersection asserted at two widths. **CU2:** R-DP9
implemented (`isNoOpDrop` guard + neutral cue). **CU3:** an empty moved-set verdict
reads "equivalent placement — nothing else moved", not blank space. **CU4:** the due
marker decoupled from the late-alarm red (neutral slate, DASHED outline) so a met due
date is not a problem; marker chips flip left near the right edge (full words, no
"…ase"); downtime cards state the window ("17:00 – 05:00") + reopen weekday. **CU5:**
+/− zoom controls (pointer/keyboard path; Ctrl+wheel unchanged) + a first-load hint;
aria-labelled (accessibility note in docs/04). **CU6:** newer-schedule detection
(pure `findNewerSchedule`, same-submission scope) offers a dismissible jump — the
stale tab now notices. **CU7:** temporally-adjacent bars carry a right-edge seam so
packed ≠ overlapping at day zoom. **Cockpit JS 137** (was 113); non-slow Python green
(1171) as a regression guard; frontend + docs + env only. See the docs/04 2026-07-18
Session 4.3 amendment.

**v2.24:** **Session 4B.1 — Glass Box instruments (hand-auditable dataset,
sabotage menu, walkthrough)** 2026-07-18 (docs/04 amendment). The instruments for
Daryn to verify — at his own pace — that the gate catches deliberate defects and
that every placement traces to a row he authored. **CU1:** a HAND-AUTHORED,
committed IDS submission at `datasets/glass_box/` (15 orders, 5 machines, ref date
2026-01-05, flat $60/h so cost = time) with the seven narrative features present
EXACTLY ONCE (alternative-group per-machine rates, a splittable op that pauses at a
closure, one order late by pure contention, a Saturday-overtime rescue, a
two-machine precedence chain, a setup_family changeover, and the comfortably-early
control) — gate ACCEPTED/C2/0-findings, deterministic solve reproduces all seven,
ledger decomposes exactly ($6956.83). A `README.md` narrates the story as
predictions AUTHORED BEFORE the solve (contradiction = a finding, not a rewrite).
**CU2:** `SABOTAGE_MENU.md` — ten keyed one-cell edits, each naming the rule caught
(a real id from the 33), outcome/severity/grade, and the certificate line, with a
false-positive CONTROL that must trip nothing; every item verified once mechanically
(`test_glass_box.py`). **CU3:** `WALKTHROUGH.md` — the session script (submit → read
+ interrogate the certificate's three registers → sabotage in batches → fix → solve
→ read the story of the solve), a per-feature question/receipt table, and the ORD-05
trace exercise (CSV row → gate → canonical entity → solver placement → cost ledger →
"why" answer). Exit bar: "you tried to catch it lying and could not." **CU4:**
`dev_api.ps1 -Scenario glass_box` copies the committed dataset into `_data/mrd`
(no generator); ledger + LLM env already flow so audit questions are recorded.
**19 new tests** (1 clean + 10 sabotage + 8 story); full non-slow Python green;
frontend untouched. See the docs/04 2026-07-18 Session 4B.1 amendment.

**v2.23:** **Session 4B.0 — IDS alternative-resource doorway: per-alternative rates**
2026-07-18 (docs/04 amendment). Connector-track opener. The alternative-resource
doorway (docs/06 §5.3) was half-built: eligible *sets* entered through the CSV since
Session 3.1, but per-alternative *rates* did not. **CU1 (adapter truth, test-first):**
`IDSAdapter` grouped repeated `(route_id, sequence)` rows into one `explicit_set`
OperationSpec (not last-wins, not two ops, not a crash) but read the time model from
the FIRST ROW ONLY — silently dropping every alternative's own
`run_minutes_per_unit`. The existing multi-eligible scenario DID enter through the
CSV doorway (so B2 pipeline-proof for eligible *sets* was not one-sided); it was
per-alternative *rates* that were unproven. **CU2 (spec):** docs/06 → v0.5 (§5.3
alternative groups: per-alternative setup/run → `rate_overrides`; step attrs must
agree; `active=false` removes a row; zero active = unroutable; identical triples =
duplicates; `role` reserved); docs/01 §5.5 `ResourceRequirement.rate_overrides`;
registry → **33 rules** (`ids.alternative_step_attributes_agree`, AMBIGUOUS_SOURCE,
first-row-wins). **CU3 (implement):** the adapter captures per-alternative
`rate_overrides`; the Planner projects them onto per-resource durations; the Solver
Builder builds a **variable-duration** encoding for a heterogeneous op (homogeneous
ops keep the exact scalar path → byte-identical goldens, the no-map guarantee); the
extractor prices the chosen machine honestly. **CU4 (pipeline proof):** new
`multi_route_rates` generator scenario (per-alternative run times through the CSV,
equal rates so price is purely duration) + a counterfactual that pins the slow
alternative and asserts a duration exactly 60 min longer and strictly higher cost,
priced end to end — B2 pipeline-proven honestly. Named debts: resumable-op +
rate_overrides (uses scalar default), heterogeneous-op pin conflict-detection scalar.
Non-slow Python **1160 passed, 0 failed**; goldens byte-identical. See the docs/04
2026-07-18 Session 4B.0 amendment.

**v2.22:** **Session 4.2 — planner surface pass 1 (read layer only)** 2026-07-17
(docs/04 amendment). The cockpit now reads like a planner's board: capacity-state
backgrounds (off-shift / closure / planned-maintenance / overtime / open-idle,
CU1), a reference-date now-line + due/release markers (CU2), planner-voiced job +
downtime hover cards (CU3), per-row utilization / booked-through / next-open-gap
(CU4), and operation anatomy — setup segments, split-op kinship, the unified
pin/lock marker (CU5). Both themes, all tokenized/feel-tunable. Contract **1.5 →
1.6** (additive: `CalendarWindow.reason`; `ServiceOutcomeBlock.customer_name /
quantity`; `ResourceLane.booked_through / next_open_gap`). No interaction/solver
changes — everything renders only what the model can source truthfully; row
intelligence is computed via `row_intelligence.py` / `rowstats.js` over the
solver's own flattened windows, pinned by shared fixtures. **Named debts (R-AI1):**
unplanned-downtime doorway (no observed-actuals channel — the band slot is
reserved, not painted); utilization/gap have NO ask route yet (AI-track 2). Rider:
the dev question-ledger empty state reworded to planner-comprehensible copy.
Non-slow Python **1148**; cockpit JS **113**. See the docs/04 2026-07-17
Session 4.2 amendment.

**v2.21:** **AI-track Session 4A.1c — the testimony validator passed FABRICATED
record citations** 2026-07-17 (docs/04 amendment). LLM answers footnoted records
that don't exist (`[record: Nothing scheduled for all]`,
`[record: evidence_chain_001]` — screenshots), and "is there a better schedule"
answered with a schedule LISTING (prose) instead of a refusal. **Issue traced:** the
4A.1 validator checked timestamps/numbers/machines + that SOME footnote existed, but
never that a cited id is REAL; and `classify` matched the bare word "schedule" in
"is there a **better** schedule" → a listing (a deterministic mis-route of an
optimality question). **Fixes:** (A) `_build_prompt_material` also returns
`known_records`; `_validate_testimony` rule 5 — every `[record: X]` must prefix a
real bundle record id, else regen → template fallback (the `?` placeholder exempt).
(B) `LLMRenderer.render` short-circuits to the template BEFORE any LLM call when the
bundle has no evidence chain (refusal / near-miss / clarify / empty listing have
nothing to testify from — the model could only fabricate). (C) new
`_OPTIMALITY_TRIGGERS` suppress the schedule-listing route on better/best/optimal/
improve/cheaper phrasings → "is there a better schedule" falls to `unsupported` → the
honest refusal (rendered verbatim by fix B). **Tests:** `test_testimony_validation.py`
(fabricated id + prose-as-citation rejected; real-prefix passes; empty/refusal bundle
never calls the client — `calls == 0`); `test_interpreter.py` (better-schedule →
unsupported/REFUSED, normal listing still routes); `test_ask_chain_api.py` slow
(better-schedule refuses citing no records; an injected fabricating LLM degrades to
template). **Non-slow Python green** + ask-chain 12/12; frontend untouched. Lesson:
"cite a record" ≠ "cite a REAL record" — validate the id against the bundle, and
never hand the model an empty evidence chain.

**v2.20:** **AI-track Session 4A.1b — the ask endpoint 500'd with a real API key
(mocked fail-closed ≠ real-path fail-closed)** 2026-07-17 (docs/04 amendment).
With `ANTHROPIC_API_KEY` set and the DEV build's `llm: true`, a **taxonomy-shaped**
question that routes DETERMINISTICALLY ("why is ORD-000004 on F001-RES002?")
returned **HTTP 500** on `/ask`. **Diagnosis:** the 4A.1 fail-closed tests all
injected a MOCK client, so the real `_call_llm` call site was never run;
`anthropic.Anthropic(bad_key)` does not raise (a bad key surfaces only on the first
CALL), and `render()` had **no try/except** around `self._client.messages.create(...)`
— its `anthropic.AuthenticationError` (a non-`ImportError`) propagated out of the
synchronous handler → 500. The layer is response/request execution in the RENDERER;
a deterministic route still renders through the LLM. **Fix (defense in depth):**
`LLMRenderer.render`/`_render_register`/`render_judgment` each wrap the whole
LLM-touching body in one `try/except` → deterministic TEMPLATE via a single
`_template_fallback` (never raises); `LLMRenderer`/`Interpreter` construction
broadened `except ImportError` → `except Exception`; the API `/ask` path adds the
outer belt — deterministic re-route on a routing raise + the single
`_render_fail_closed` render seam, both logging `EVENT ask.llm_degraded`. **Tests
(the missing real-path):** `test_ask_chain_api.py` `TestAskFailClosedWithRealKey`
drives the endpoint with a genuine (invalid) key + `llm:true`, injecting an auth
failure / a garbage response / a raised exception — each **200 + `[rendered by:
template]`**; plus the CU3 ordering test (both interpreter and renderer forced to
raise → the taxonomy question still routes `late-orders`/`deterministic` and
renders). Fast unit coverage in `test_render_fail_closed.py` (8) on the unmocked
renderer. **Non-slow Python 1126 passed** (+8) + slow ask-chain 10/10; frontend
untouched. Lesson: a fail-closed guarantee proved only against a MOCK is unproven —
exercise real construction and the real call site, and seal the RENDER path, not
just the router.

**v2.19:** **Session 4.1 — light theme as the shipped default; theme as a
first-class token dimension** 2026-07-17 (docs/04 amendment). Product decision
(Daryn's charter, ratified): this product's visual language is TRUST — the document,
the ledger, dark ink on light paper; the dark cockpit signalled *developer tool*.
**Light is now the shipped default; dark is an option** — and light is a DESIGNED
theme, not an inversion. **CU1 architecture:** `tokens.css` split into a STRUCTURAL
layer (typography, spacing, geometry, motion TIMING, feel-panel opacity multipliers
— theme-invariant) + two COLOR files (`theme-light.css`, `theme-dark.css`) selected
by a `data-theme` attribute (light declared for a bare `:root` too → no flash on the
default path; a no-flash `<head>` script + a chrome toggle + `?theme=` URL/config
param; theme choice is a tier-2-class preference). **CU2 the light palette:** warm
paper bg, dark-slate ink, a **deuteranopia-safe lateness palette** (on-time BLUE +
tight/late separated by LIGHTNESS *and* ink polarity — three redundant cues, all AA
on their fill), shading re-tuned for paper (dim-dominates-green carries as
SEMANTICS; opacities re-tune at the feel panel), ghosts/traces/tentative-hatch
redrawn (new `--carry-ink`/`--tentative-ink`/`--tentative-backing` — the tentative
hatch's hard-coded white label was the one place an inversion failed silently),
standing-pin amber vs pin-lock green both re-tuned. **Dark kept working — colors
moved VERBATIM; no design effort on dark this session.** **CU3 contrast + harness:**
micro-chip typography bumped for AA both themes; the Playwright harness parametrized
on `data-theme` via projects (logic once + light/dark run every rendering spec) — C1
drift asserted per theme. **Cockpit JS 94 passed** (logic 6 + light 44 + dark 44;
was 49 single-theme); Python untouched (frontend-only), non-slow suite green as a
regression guard. Note for Daryn: visual opacities re-tune on light at the feel
panel; semantic/motion tokens stand. Queue before Phase-4 design unchanged: Daryn's
grand feel pass + export.

**v2.18:** **Session 4.0e — accepted placements are standing commitments (R-DP8)**
2026-07-17 (docs/04 amendment). Live: an accepted, then PUBLISHED, edit was
silently reverted by the next edit's re-solve — the delta card honestly listed the
reverted op as a "consequence," but a placement the planner committed should not be
movable at all. Cause: the re-solve pinned only the ONE op being dropped; every
prior accepted pin was free again, so the optimizer undid a cost-neutral move to
recover a few dollars. **Ruling (R-DP8):** an accepted pin persists in the lineage
as a STANDING constraint — compiled into EVERY subsequent sandbox/accept/scenario
solve until an explicit (future) `unpin`. **CU1 persistence:** cumulative lineage
pins live on the version (`schedules.pins_json` + a migration); a single seam
`src/mre/modules/standing_pins.py` applies the primary drop AND the standing pins
through the SAME `apply_pin` (both axes mandatory), and NAMES a blocking commitment
on a provable overlap (`VariableMap.op_durations`) rather than quietly sacrificing
the older pin. **CU2 visibility:** contract **1.4 → 1.5** (`AssignmentBlock
.standing_pin`) → a subtle persistent standing-pin marker on committed bars, and a
standing-pinned op is STRUCTURALLY excluded from every moved-set (never a
consequence). **CU3:** `tests/test_standing_pins.py` — the two-edit chain (A
accept+publish, B accept → A unchanged, in no moved-set) + conflict-refusal +
fast units/migration; `gesture.spec.mjs` drives it visually. **Non-slow Python 1118
passed** (+15) + slow `standing_pins`/`planner_edit`/`sandbox`/`scenario` green,
goldens byte-identical; **cockpit JS 49/49**. Release (`unpin`) named as a
carry-forward. Queue before Phase-4 design unchanged: Daryn's grand feel pass +
export.

**v2.17:** **Session 4.0d — MAX_PATH survives the bound (the 4.0c fix was validated
in a short prefix)** 2026-07-16 (docs/04 amendment). Live: post-4.0c, **every**
accept still failed `FileNotFoundError [WinError 3]` — now even on a **fresh
schedule, depth-1 edit**. The 4.0c cap of 90 chars was calibrated against a short
temp-dir prefix; Daryn's real data root spends ~130 chars before any snapshot id,
so a chain grown near the cap still crossed 260. **Fixed all three, defense in
depth:** (1) **long-path seam** — new `src/mre/modules/longpath.py` routes the
snapshot/run store's I/O through Windows `\\?\` extended-length paths (the 260
limit stops applying); `SnapshotStore`/`prepare_out_dir`/accept-`copytree`/
`_persist_document` all go through it. (2) **short opaque snapshot ids** —
`_edit_snapshot_id` is now a fixed-width `snap-edit-<sha12>` (22 chars) embedding
NO lineage (the parent chain lives in the registry), so the on-disk name is tiny
however deep the chain. (3) **boot / `/health` path-budget tripwire** —
`longpath.path_budget` warns loudly at startup when a data root is deep enough to
exceed 260, and `/health` carries the numbers; never discovered at accept time
again. **Tested at a REALISTIC prefix:** `test_longpath.py` (a SnapshotStore
round-trip at a >260 path + a naive negative control), a rewritten
`test_edit_snapshot_id.py` (opaque/fixed-width), and a **slow end-to-end accept
under a ~160-char-prefix data root** where a 4.0c-era id would have crossed 260.
**Non-slow Python 1103 passed** (+7) + slow `planner_edit` **11/11**; cockpit
untouched (JS 48/48). Queue before Phase-4 design unchanged: Daryn's grand feel
pass + export. Named residual: the shallow run-dir writers (evidence sink,
certificate) are not yet on the seam — safe at Daryn's depth, flagged by the
budget check for absurd (>200-char) roots.

**v2.16:** **Session 4.0c — the silent accept (an accept that 409'd on a storage
limit, rendered mutely)** 2026-07-16 (docs/04 amendment). Live specimen: schedule
`ea1a42f0` — sandbox verdict succeeds, Accept pressed, bar returns home with **no
error** and the **same id** (no new version). **Diagnosed against the live
registry first:** `ea1a42f0` has **no child** and is `proposed` (not superseded) →
accept didn't commit and wasn't a supersede-409 (suspect 3 refuted); the `runs`
table showed **11 failed accept runs, all with the identical**
`FileNotFoundError [WinError 3]` (suspect 2 confirmed, suspect 1 — the hotfix's
post-condition — refuted). **Mechanism, reproduced:** each accepted child was
minted `f"{base}--edit-{hash}"`, appending unboundedly; `ea1a42f0`'s id is a
**7-deep, 118-char** chain, and at that depth the snapshot dir path crosses
Windows **MAX_PATH (260)** → the child derive fails, accept 409s, and the cockpit
hid the card + reason on the failure branch. **CU2 fix:** `_edit_snapshot_id`
bounds the id (≤ 90) — shallow chains stay readable, deep ones collapse to
`{root}--chain-{sha12}--edit-{hash}` (fixed-width however deep); lineage lives in
the registry's parent chain. **CU3 (regardless of cause):** a refused accept is
now **LOUD** (R-M1a) — an authored refusal card (`showRefused`, "Edit not saved",
raw reason kept as a muted detail) + a shake, never a silent bar-goes-home. **CU4:**
the DEV question-ledger refusal panel (4A.1) was floating over the ask composer —
now docked bottom-**left**, collapsible, collapsed by default. Post-condition
hardened to compare in canonical minute units explicitly. **Non-slow Python 1096
passed** (+4) + slow `planner_edit` 10/10; **cockpit JS 48/48** (was 47). Queue
before Phase-4 design unchanged: Daryn's grand feel pass + export.

**v2.15:** **Session 4.0b — Tier-0 vs solver eligibility: one source of truth
(R-DP6)** 2026-07-16 (docs/04 amendment). The 4.0-hotfix left open whether Tier-0
could *green* the un-pinnable row it defended against. Eligibility was resolved
TWICE by hand — the Solver Builder (which resources get an `op_assign` literal,
the set the pin binds) and the assembler (the payload's `eligible_resource_ids`).
**CU1:** the payload advertised the RAW capability set (`op_eligible`) while the
pin binds the COMPILED set (`op_assign`), which the builder further prunes for
**resumable** ops (no in-horizon calendar window) and **WIP** ops (no free
literal) → `payload ⊇ solver_literals`, so Tier-0 could offer a row the pin then
silently skips. A probe found **0/100 ops diverge** on `multi_route_distinct` +
`busy_board` (both `splittable=0, wip=0`) — the gap is **latent**, then reproduced
on a constructed resumable op. **Live case:** ORD-000002's RES001 op is
capability-DIM on RES002 (payload and solver AGREE), so the data was honest and
refusal enforcement (`drop()` refuses `!legal`) intact — the symptom was the
pin-skip the hotfix already closed. **CU2 unify:** new ortools-free
`eligibility.py` holds the SINGLE `capability_eligible` + `feasible_window_range`
+ `flatten_resource_windows` + `pinnable_resources`; the Solver Builder delegates
(goldens byte-identical), the assembler derives the payload through the same
functions → the two sets equal by construction. Contract **1.3 → 1.4** (additive
`dim_reasons`; `eligible_resource_ids` narrows to the solver-pinnable set); the
cockpit dims a pruned row with its truthful reason ("no open calendar window").
**CU3 guard:** `test_eligibility_consistency.py` asserts payload == op_assign for
every op on both fixtures + the constructed resumable case; a `legality.spec.mjs`
row-type test (eligible/capability-ineligible/solver-pruned → takes/dims/dims).
**Non-slow Python 1092 passed** (+6) + the slow eligibility guard; **cockpit JS
47/47** (was 46). Queue before Phase-4 design unchanged: Daryn's grand feel pass +
export.

**v2.14:** **Session 4.0-hotfix — an accepted cross-machine drop landed on the
wrong machine (R-DP1 violated in shipped code)** 2026-07-16 (docs/04 amendment).
Live: drag RES001→RES002, verdict "+0.30% proven," Accept → the op rendered back
on RES001 (right time, wrong machine). **CU1 diagnosis by evidence:** the pin was
`lit = op_assign[op].get(resource); if lit is not None: model.add(lit == 1)` in
both `sandbox.py` and `planner_edit.py`; `op_assign[op]` keys only the op's
*eligible* resources, so a target with no literal → the machine pin **silently
skipped**, the time pin binds alone, the re-solve relocates the op to its cheaper
eligible machine and reports a feasible verdict for a placement never tested.
Reproduced deterministically: an eligible id-matching pin binds and reproduces the
reported +0.30% exactly (honest); an un-pinnable target gives feasible/0.0% with
the op on the incumbent (the symptom). Sandbox and accept share the pin (identical
code + params) — cannot diverge. **R-DP1 was violated in shipped code:** the
machine axis was offered, not enforced, then vouched for. **CU2 fix:** the machine
pin is mandatory — accept raises (API 409, base stands) + a post-solve R-DP1
post-condition; sandbox short-circuits to an honest INFEASIBLE return-home instead
of a false delta. **CU3:** the 3.4/3.8 suites pinned only same-machine and never
asserted placement — added `TestAcceptHonoursThePinnedResource` (slow,
`multi_route_distinct`: cross-machine accept lands on the pinned resource+start;
ineligible pin refused, never relocated) + a `gesture.spec.mjs` cross-machine
drag→accept→rebind rendered-row assertion + the same end-state check in
`rehearsal.spec.mjs` Beat 4. **Non-slow Python 1086 passed** (planner_edit slow
10/10, sandbox 12/12); **cockpit JS 46/46** (was 45). Queue before Phase-4 design
unchanged: Daryn's grand feel pass + export.

**v2.13:** **AI-track Session 4A.1 — R-AI1 ruling + the interpreter, conversational
context, and the question ledger** 2026-07-16 (docs/04 amendment). First AI-track
session; implements **R-AI1** ("everything logs facts and establishes pathways to
AI"). The M10 deterministic router is refactored so `answer() == route(*classify())`
— a **closed 15-route taxonomy** (`ROUTE_TAXONOMY`) callable by everything, routing
byte-for-byte unchanged (zero regression, the deterministic path never touches an
LLM). **CU1** the **interpreter** — free-form phrasing → (route, params, confidence)
onto the taxonomy ONLY, invoked only on a deterministic miss; LLM-backed, strict
JSON, **fail-closed** (no key / malformed / low confidence → honest refusal); params
resolve through the identity map (external refs in, no id-shape regex); the
paraphrase table is the growing asset the ledger feeds. **CU2** **conversational
context** — deterministic ellipsis resolution before routing ("and what would fix
it?" → against the last order; "how much?" after an edit → the edit-cost domain),
**visible** (the resolved question rides back, the cockpit shows an "interpreted as"
note); unresolvable ellipsis → clarify, never a guess; server stays stateless (the
cockpit carries a 4-turn history + selection + session id). **CU3** the **question
ledger** — every ask logged as a `QuestionLedgerEntry` in its OWN JSONL stream
(never schedule evidence): verbatim + resolved question, route/REFUSED, confidence,
register, version, and **rephrase linkage** (a refusal → its later successful
rephrase = free labeled data); a DEV-gated cockpit refusal-cluster panel +
`GET /ledger/refusals` (404 unless `MRE_DEV`); a **meta-route** reads the ledger
itself. **CU4** **tiered fallback** — a near-miss bridge (moderate confidence /
partial params → the two nearest routes as authored one-phrase offers) between
routed and refused; no dead ends, all fallback copy authored. **1086 non-slow
Python** (+50) + the slow ask-chain ladder; **cockpit JS 45/45** (was 44). **Debts
named** (R-AI1 close-out, AI-track Session 2/3): WIP has no question domain,
cross-run economics has none, constraint-catalog "why can't it do X" is not
conversational. See the docs/04 2026-07-16 R-AI1 + Session 4A.1 amendments.

**v2.12:** **Session 3.8 — version-lifecycle continuity in the cockpit** 2026-07-16 (docs/04 amendment). Feel-pass findings: after an accept→publish the cockpit stayed bound to the *superseded* schedule id → `/ask` returned a raw "superseded" error, a subsequent accepted drop *returned home*, and Tier-0 shading rendered from the stale payload ("zombie legality"). **CU2 (diagnose first)** — reproduced against the real API: a stale-bound board's `/sandbox` + `/accept` **409 against the superseded id (the backend never commits)** — so the returned-home drop was NOT a committed edit reverting; it was the accept *failing* against a stale id — while `/interaction` still 200s (no status guard) → the zombie legality. Backend lifecycle is correct; the defect is the cockpit's version binding + its handling of a superseded response. **CU1** — every version change (accept AND publish) now routes through one seam that updates the **URL** (`history.replaceState`), the strip, the ask target, the **selection** (cleared), and the hook; the controller already re-fetches the new version's interaction + alternatives. Invariant: no user action may be issued against a superseded id from a live session. **CU3** — additive `Registry.live_successor` + `successor_id` on a superseded `/meta`; a typed `ApiError.superseded`; a **deep link** to a superseded id loads read-only behind a banner + a one-click "View current" jump, gesture surface **not wired** (no editable zombie); a **live** 409 self-heals (planner language + jump). **Harness** — the fixture server models the lifecycle (records parents, supersedes on publish, 409s superseded ids, serves `successor_id`, composes the edit chain's pins, `POST /__test__/reset` before each boot); three new tests: two consecutive edit→accept cycles, edit→accept→publish→edit, and the superseded deep link. **Cockpit JS 44/44** (was 41); Python **1036 non-slow** + planner_edit slow 7/7 (new successor test). Queue before Phase-4 design unchanged: Daryn's grand feel pass + export. See the docs/04 2026-07-16 Session 3.8 amendment.

**v2.11:** **Session 3.7 — voice input hardening (bug + interaction model)** 2026-07-15 (docs/04 amendment). A bug seen live: press-and-hold recording streamed the interim transcript into the composer, reflowed the panel, and shifted the mic button out from under the pressed pointer → `pointerup` stopped capture early and only a fragment was submitted. **CU1** — the interim transcript now renders in a fixed-footprint FLOATING overlay (never reflows the mic row — R-M1 spirit); only the FINAL transcript lands, and only on stop. **CU2** — press-and-hold → **tap-to-start / tap-to-stop toggle** (explicitness preserved: the mic never opens itself); unmistakable recording state (tokenized mic `.recording` fill/pulse + a "recording" overlay dot/label); **Escape cancels** without submitting; an optional **2.5s silence auto-stop** (`VOICE_SILENCE_MS`) as a convenience, OFF by default. The recognizer runs continuous + accumulates finals across events (keeps the whole sentence, not a fragment). All voice visuals tokenized in `tokens.css`; reduced-motion respected. Three new harness tests (fake `SpeechRecognition` drives the real path): recording toggles, **mic bbox unchanged during interim** (≤0.5px), and the **fragment regression** (full sentence submitted). **Cockpit JS 41/41** (was 38); Python untouched. Queue before Phase-4 design unchanged: Daryn's grand feel pass + export. See the docs/04 2026-07-15 Session 3.7 amendment.

**v2.10:** **Session 3.6 — R-M1 implementation (motion carries register)** 2026-07-15 (docs/04 amendment). Animation only; the ruling implemented as written, consuming the 3.5 motion tokens. **CU1 REJECTION** — return-home is a fast snap-back (non-settling ease) + a brief arrival shake, the reason staying in the text channels. **CU2 REFLOW** — one implementation unifying the consequence motion + the 3.4 accept-rebind: simultaneous eased transitions (a single `.reflowing` class, `transition-delay:0` — explicitly no per-bar stagger, since CP-SAT re-solves globally), displaced bars briefly highlighted. **CU3 OWN PLACEMENT** — the dropped bar never slides (`:not(.pin-lock)` excludes it from the reflow); it snaps to its committed spot with a static green pin-lock ring, distinct from the tentative. **CU4 GHOSTS** — fade in/out only, labels fading WITH their bars (both layers), covering precomputed + on-demand arrival. Reduced motion respected (a single `@media` block → instant; classes/semantics intact, rejection still distinct via text). Four motion end-state harness tests added; **cockpit 38/38**; Python untouched. **Queue before Phase-4 design: exactly Daryn's grand feel pass + export** (the panel now exposes every visual + motion token). See the docs/04 2026-07-15 Session 3.6 amendment.

**v2.9:** **Session 3.5 — R-M1 ruling + cockpit design-token pass (visual only)** 2026-07-15 (docs/04 amendments). **R-M1 — MOTION CARRIES REGISTER** ruled (transcribed verbatim; implementation is Session 3.6): bar motion is communication, each class a fixed meaning — (a) rejection = fast snap-back + subtle shake, never a settle; (b) reflow = smooth SIMULTANEOUS eased transitions (~300–400ms), not cascaded (CP-SAT re-solves globally); (c) own placement = never moves, a static pin-lock; (d) ghosts = fade only, labels fade WITH their bars. **The token pass** consolidated every cockpit palette/typography/geometry/elevation/motion value into `tokens.css` (grepping the CSS for a bare hex or px font-size now returns nothing), added the R-M1 motion tokens NAMED-BUT-UNCONSUMED (panel-tunable now via `feel.js` `motion.*` + `applyFeel` mirror; the tuning panel gained group headers + the motion/geometry groups), and applied a restrained modernization within the architecture (calmer chrome, cleaner 4px bars + subtle sheen, better `--font-ui`/`--font-mono` typography, unified elevation) — sleek, not flashy. Zero behavior changes; **cockpit 34/34 unchanged** (screenshots gitignored/not pixel-compared; C1 drift ≤1px still holds). Carry-forward: **Session 3.6 — R-M1 implementation** queued. See the docs/04 2026-07-15 R-M1 + token-pass amendments.

**v2.8:** **PHASE 3 EXIT — AUDITED & COMPLETE (qualified)** 2026-07-15 (docs/04 amendment). A fresh audit session ran the six exit clauses LIVE on the real dev stack (uvicorn + `busy_board`, deterministic). **One seam found and fixed in-session:** the delta card rendered the SCALED solver objective delta as dollars (Clause 2 — it would have shown "+$602" for a true ledger delta of "+$5.02", ~120×); fixed so the card shows ledger dollars (`cost_delta_abs` from a no-persist extraction; the accept response carries the decomposed `cost_delta`) and degrades to a relative-% label when no ledger figure is available — re-verified live ("+0.01% cost · +$5.02", decomposing exactly). Clause 1 (the sixty-second script, twice, deterministic legs agree; accept→Decision→publish→supersede→pool-invalidation→summarize all verified) PASS-qualified (sandbox ships the honest FLAGGED card on busy_board within the 15 s budget; LLM off — no key; voice driven programmatically). Clause 3 (R-DP) PASS via the harness. Clause 4 baselines recorded LIVE: first-grab ghosts **6.2 s**, cached **3.6 ms**, sandbox **15 s = budget**, grab→shade **5.2 ms**. Clause 5 (cold stranger) **MET-BY-PROXY** — the cold-drive is a named Phase-4 entry condition. Carry-forwards inventoried (feel tokens NOT yet exported/committed — runs on defaults; cloud in-cloud; slice-awareness; etc.). **1036 non-slow Python passed (0 failed) + cockpit 34/34.** Entering Phase 4 preparation. See the docs/04 2026-07-15 Phase 3 exit-audit amendment.

**v2.7:** **Session 3.4 — the interim final: accept/publish, the answering edit, voice, latency, the sixty-second rehearsal** 2026-07-15 (docs/04 amendment). The last build session of Phase 3, ending with the exit-demo script running end to end. **CU1** (headline) Accept is REAL: an accepted edit records a `planner_edit` Decision (basis=observed, authority MANDATORY; new `Decision.authority` field + decision_type, docs/02) and mints a NEW proposed version — **the base is never mutated** ("accept CREATES, never overwrites"); Publish (proposed → published) supersedes the prior version + invalidates its pools. Backend `planner_edit.py` (pin + re-solve + extract into a child snapshot); API `POST /accept` + `POST /publish` (`Registry.publish_schedule`); the registry is the live-status source of truth (the strip reads `/meta`); chained edits inherit the reference date from the ROOT solve (the 3.3b trap avoided). Cockpit: the delta card walks verdict → accepted → published, `board.rebind` settles the moved bars into place (R-DP7, not a teleport-reload), the controller + ask panel retarget the new version. **CU2** the sandbox/edit question domain (from a live "why does this move cost 261"): `_summarize_edits` (the closing beat) + `_explain_edit_cost` (production/setup/tardiness Δ, decomposing exactly + the 3.3 "why" clauses) over the `planner_edit` Decisions — no new answer path; the Decision carries the decomposed delta as self-contained evidence. **CU3** voice: `voice.js` push-to-talk (Web Speech, feature-detected, degrades without drama) into the SAME ask path (the deterministic router IS the taxonomy mapper, its "unsupported" bundle IS the refusal); spoken response leads with the register aloud + a one-sentence summary and NEVER voices record ids. **CU4** ghost latency: pricing fires on pointer-DOWN (dial b) + the K per-machine solves parallelize under a bounded pool (dial c); grab→shade 5.2 ms measured. **CU5** the rehearsal (`tests/cockpit/rehearsal.spec.mjs`): the sixty-second script driven beat by beat, screenshot-asserted, each beat's latency recorded — every beat green. Cockpit JS **34/34**; Python **1035 non-slow** + the new slow ladder. **Phase 3 build work COMPLETE — awaiting the exit audit.** See the docs/04 2026-07-15 Session 3.4 amendment.

**v2.6:** **Session 3.3 — Tier-1 coverage + card explainability** 2026-07-14 (docs/04 amendment). Five feel-session findings, all about the Tier-1 promise failing QUIETLY or INCOMPLETELY (the mechanics held). **CU1** (coverage) the forced-alternative heuristic WIDENED — late-demand ops + the top-N most-EXPENSIVE ops (config token) + the slack catch-all — PLUS an ON-DEMAND path: grabbing an uncovered op fires its solves right then (`build_op_alternatives` + `POST /schedules/{id}/alternatives/op/{op}`), pricing EVERY eligible machine (K': `add_required_resource_cut`, not one cut), appending to the same pool so the second grab is instant; a "pricing alternatives…" shimmer means absence is never silent; the solve bill is guarded by per-op machine + time caps and an API concurrency cap + in-flight dedup. **CU2** (bug) the empty `alternative_placement.work_orders` fixed — ghost placements + API docs speak external refs end to end. **CU3** (explainability) each MAJOR delta-card consequence gains a one-clause "why" (`_annotate_move_reasons`, threshold token) sourced from the re-solve's own occupancy arithmetic — "blocked on <machine> until <time>" / "displaced by the dropped op" — rendered in planner vocabulary, never fabricated. **CU4** (completeness) drop-onto-ghost now lazy-fetches the ghost's member document and traces the FULL moved-set ("consequences loading…" until it lands, R-DP7), not just the dropped bar. **CU5** (guards) the certificate + IDS end-to-end suites skip feel fixtures explicitly (the `busy_board` reds retired); `SandboxResult` echoes its applied time limit so budget-vs-actual is always inspectable. Cockpit JS **30/30** (7 board + 5 legality + **18** gesture); Python non-slow green (+ new slow on-demand + reason tests). See the docs/04 2026-07-14 Session 3.3 amendment.

**v2.5:** **Session 3.2d — feel-session fixes** 2026-07-14 (docs/04 amendment). Six items from a live `busy_board` session with Daryn's hands on the gesture surface. **CU1** (bug) Tier-0 shading now clears on the **drop→tentative** transition — 3.2c had only covered idle-entry paths; `clearLegalityOverlays()` retires the wash + ghosts on drop and `redraw()` no longer repaints them past the dragging phase (new harness test observes `shade === 0` in-flight through verdict). **CU2** (honesty) the stubbed Accept button now READS as inert (dimmed, not-allowed, no hover) with a planner-facing tooltip. **CU3** (bug) the deictic "Why is this here?" seam hardened: an order-less selection keeps the button disabled with a hint (no dead enabled control), and programmatic `board.select()` now fires the shared-selection callback so the scope never goes stale — the router is untouched, seeing only fully-resolved external refs (new test asserts the resolved question is sent, non-fallback answer rendered). **CU4** (wording) the unsupported-question menu reworded from `WO-XXXX / M-YYYY / snap-a` id-shapes into planner language, led by concrete examples from the loaded schedule's real refs where cheap. **CU5** (feel) two shading-emphasis knobs added (`shade.green_opacity` / `shade.dim_opacity`) as tuning-panel sliders, defaults letting dim + ghosts dominate green — tokens first, the inversion decision waits on Daryn's verdict. **CU6** (investigate→wire) the LLM renderer path was already built + fail-closed and config-only; wired for the dev build (`llm` flag when `import.meta.env.DEV`), documented in the cockpit README (key via the API env, never committed). Cockpit JS **26/26** (7 board + 5 legality + **14** gesture); Python explainer **129 green**. See the docs/04 2026-07-14 Session 3.2d amendment.

**v2.4:** **Session 3.2c — the drag/pan conflict fix** 2026-07-14 (docs/04 amendment). A live-on-`busy_board` bug: dragging a bar sideways panned the whole timeline (vis-timeline's built-in Hammer pan on the center container ran alongside the controller's bar-carry; `preventDefault` in the pointer path never touched it). Latent through 3.2b because the harness drives the phase machine through the programmatic `window.__cockpit.drag` hooks, which emit no Hammer events — the conflict lives only on the real pointer path. Fix: `board.setPanZoom(enabled)` toggles vis's `moveable`/`zoomable` (the vendored `Range._onDrag` re-checks `moveable` on every panmove, so options hold mid-gesture — no Hammer surgery); the controller suppresses on pointer-down over a bar (still from the first pixel) and restores on pointer-up (pan resumes the instant the bar is released, so tentative/verdict stays pannable). Verified by a new real-pointer harness test (window bit-for-bit unchanged mid-drag; **negative-control run** proved it bites — window jumped a day with the fix stubbed out) and a shading-lifecycle check (already correct: no wash survives to an idle board; regression pins added). Cockpit JS **24/24** (7 board + 5 legality + **12** gesture); Python untouched. See the docs/04 2026-07-14 Session 3.2c amendment.

**v2.3:** **Session 3.2b — interim-B part 2, the gesture surface, COMPLETE** 2026-07-12 (docs/04 amendment). **interim B is complete.** The interaction layer rendered against `multi_route_distinct` (realistic rates → the priced ghosts are the forced-alternative service's). **CU1** grab → Tier-0 shading (`drag/shade.js`): green legal / amber displace / dim, capability-dim distinguished, hover-over-dim one-line reason; standing latency regression grab→shade **< 100 ms** (the bake-off bar; payload prefetched, R-T1d). **CU2** ghosts (`drag/ghosts.js`, R-T1a): forced-alternative + pool placements unified, source-distinguished subtly, each wearing its price / "not feasible this horizon" verdict, labels legible + tracking (ghost drift ≤ 1 px). **CU3** drag physics (`drag/magnets.js`, pure; R-DP1/R-DP3): semantic snap from the anchor set (ghosts strongest → calendar → adjacency → predecessor → coarse grid), resolves during the drag, Alt disables, dim refuses with boundary-pinning + not-allowed cursor, release-over-dim returns home animated. **CU4** drop → tentative → verdict (`drag/controller.js` + `drag/sandboxui.js`, R-DP2/R-T1c): hatched tentative bar, `POST /schedules/{id}/sandbox` with a visible countdown, three honest outcomes (delta card / flagged "bound not proven" / return-home), drop-onto-ghost near-instant from the vouching schedule; **accept STUBBED DISABLED** (no publish workflow — a dead-end accept would break R-DP7). **CU5** change traces (`drag/traces.js`, R-DP7): the moved-set drawn old→new (ghost-of-old + motion line) held until discard, delta-card line items linked to bars (click → navigate + pulse), discard restores everything. **CU6** the tuning panel (`drag/tuning.js`, DEV-BUILD-ONLY): every feel token live with hot reload + export — the feel-iteration instrument, never in the production build. Backend spine (additive): `sandbox.py` moved-set + `POST /sandbox`, forced-alternative `alternative_placement`, a distinct-rate cockpit fixture (ghosts + canned sandbox). **1026 Python tests + cockpit JS 23/23** (7 board + 5 legality + 11 gesture). Carry-forwards: accept/publish (final), voice (later interim), slice-awareness (pilot-gated), one-ghost-per-op, and the feel iteration. See the docs/04 2026-07-12 Session 3.2b amendment.

**v2.2:** **Session 3.2a — interim-B part 1, the interaction data spine, COMPLETE** 2026-07-12 (docs/04 amendments). Everything interim B needs that is testable WITHOUT a cursor; the gesture/voice surface is 3.2b. **CU1** the split interaction endpoint (R-T1d): contract 1.2 → **1.3**, `GET /schedules/{id}/interaction` serves the Tier-0 block, the main document returns to ~1.1 size (a MINOR bump, ruled honestly — the schema is unchanged, the field was always optional, the sole consumer is the cockpit); cockpit background-fetches after first paint with stale-while-revalidate + a stub drag-enabled flag. **CU2** the Tier-0 legality library (`src/cockpit/legality/tier0.js`, pure/framework-free): eligible rows + legal-start regions (calendar ∩ precedence floor ∩ window-fit) + the anchor set, conservative-error asserted (never greens a proven-illegal spot, R-DP6), all four dim dimensions tested incl. resumable window-fit. **CU3** the forced-alternative service (`forced_alternatives.py`, R-T1a/b): per-op "not on the incumbent machine" re-solves stored as pool-member-class documents (`source="forced_alternative"`, same tables/exclusion/invalidation), infeasibility first-class; the price-bought-something counterfactual on the new `multi_route_distinct` scenario asserts both halves (plain pool ~0 cross-machine, forced yields priced cross-machine); API additive `POST/GET /schedules/{id}/alternatives`. **CU4** the sandbox latency budget (`sandbox.py`, R-T1c): the pure three-outcome classifier (budget a design token, budget-exhaust simulated) + a pinned re-solve; the verdict CI regression runs on the non-degenerate distinct fixture (a CU4 finding: the saturated demo fixture is degenerate by design → a within-budget FLAGGED card, never a hang). 1022 non-slow tests green (+23) + new slow ladder; cockpit JS 12/12. Carry-forwards: pool/forced slice-awareness (heavier, pilot-gated), the gesture surface (3.2b), the v1 selection heuristic. See the docs/04 2026-07-12 Session 3.2a amendment.

**v2.1:** **Session 3.1b — interim-A (read-only cockpit) COMPLETE** 2026-07-11 (docs/04 amendments). The three remaining commit-units landed: **CU3** the cockpit shell — `src/cockpit/` (Vite 5, framework-free ES modules, vis-timeline pinned to the bake-off `7.7.4`, design tokens externalized in `tokens.css`) renders a **contract-1.2 document from the live API** (resources as rows, `work_orders`/`external_name` planner vocabulary, per-Demand lateness coloring, calendar closures, top strip = contract version + certificate grade via the new `GET /schedules/{id}/meta`); read-only (`editable:false`, no drag handlers). **CU4** the ask panel — embeds M10 (`/ask`), registers render visibly distinct (testimony/judgment from the additive `bundle.register`), and the answer's cited bars + lanes light up in sync via the additive `bundle.cited_refs` (an always-on overlay tags each cited bar); clicking a bar scopes a deictic "why is this here?". **CU5** the Playwright screenshot harness promoted to `tests/cockpit/` (hermetic committed `multi_route` fixture + fixture-server, 6 scripted states screenshotted with machine-checked assertions incl. the standing **C1 label-vs-bar drift regression ≤1.0px** and a **mid-pan frame** closing the 3.0b residual; **6/6 green** headless, CI-ready). **Acceptance met LIVE** (not cited from tests): real `multi_route` solve → cockpit over the Vite→API proxy → ask "why is ORD-000012 on F001-RES002?" → **testimony answer citing the alternatives' prices** ("Same cost" / "Would cost −20.08 more", straight from the reconstructed-assignment Decision — no new answer path) → 2 cited bars + 3 lanes glow, `ACCEPTED / C1` strip, 0 page errors. 999 tests green (+4 API). Carry-forwards (interim-B/design-thread): the contract-1.2 split-endpoint `/interaction`, the drag surface (R-DP1–R-DP7), the parked pool-diversity ghost-realism question, a `renderers.py` "−N more" prose quirk. See the docs/04 2026-07-11 Session 3.1b CU3/CU4/CU5 amendments.
**v2.0:** **Session 3.1 interim-A (read-only cockpit) STARTED** 2026-07-11 — the two backbone commit-units landed (docs/04 amendments): **CU1** the `multi_route` capability-routed generator scenario (docs/05 B2 now pipeline-proven — multiple `routing_lines` rows per (route,sequence) = the eligible set; adapter grouping; `solution_pool.cross_machine_ops`; a saturated identical-rate pair makes the pool surface cross-machine ghosts at a clean base; nonzero ghost price + single-eligibility-collapse counterfactual in `tests/test_multi_route.py`) — closes the 3.0 "no legal cross-machine move in generated data" carry-forward; **CU2** schedule **contract 1.2** (additive `interaction` block: Tier-0 client-side legality payload — per-op eligible sets, durations, release floors, instance-expanded precedence; size check on clean_large = +1.9 MB/+35.7%, split-endpoint proposed for interim-B). **Remaining interim-A work (not yet built): CU3** the cockpit shell (production vis-timeline frontend rendering a contract-1.2 document from the live API), **CU4** the ask panel with cited-bar highlighting (M10 embedded), **CU5** the Playwright screenshot harness promoted to `tests/`. See the docs/04 2026-07-11 Session 3.1 amendments.

**v1.9:** **drop-pin ruling RESOLVED** 2026-07-11 → R-DP1–R-DP7 (docs/04 amendment) — open-rulings queue item 5 closed. The cockpit edit vocabulary: pin is both-as-displayed (R-DP1); commit-or-return with mid-drag refusal (R-DP2); semantic snap (R-DP3); gesture=command/language=wish with soft preferences as objective penalty terms (R-DP4, new docs/05 Category H row); HOLD/DEFER verbs (R-DP5); per-layer legality epistemics (R-DP6); change legibility — no silent swaps (R-DP7). Phase-3 drag-and-drop line + W2 + queue updated.
**v1.8:** **frontend substrate SELECTED — vis-timeline** 2026-07-11, resolving the line held open after the Session 3.0 bake-off. The 3.0b extension (`tools/spikes/frontend_bakeoff/`, throwaway) held vis-timeline to the drop ruling's four killer criteria — always-on overlay layer (0 px drift, ghost labels legible), mid-drag rejection of illegal zones (refuse + return home), one real magnet with monotonic falloff through the un-throttled `onMoving` hook, and 20/20 headless drag reliability — and it **cleared all four clean** (machine-checked + screenshots; `VERDICT.md` §3.0b addendum). Decision rule applied: all-four-pass → adopt vis-timeline; custom React/SVG is the zero-blocker fallback. Phase-3 frontend line (§Phase 3) updated. See the docs/04 2026-07-11 amendment.
**v1.7:** **Phase 2 exit audited & COMPLETE (qualified)** 2026-07-10 — a fresh audit session ran the exit prompt's five clauses live (all PASS / PASS-WITH-QUALIFICATION, fix-free); exit marked below the Phase-2 item list; qualifications carried (cloud in-cloud → 2.4b; raw_data → Phase 4; pool slice-awareness/warming → Phase 3; two quarantined catalog notes; W1 scenarios + detectors). **Entering Phase 3.** See docs/04 2026-07-10 exit-audit amendment.
**v1.6:** the **Conversational Certificate landed** 2026-07-10 — frozen remediation catalog v1 (`src/mre/catalog/`, 32 rule notes + 18 fallbacks, typed + completeness-tested), three registers (testimony / remediation / judgment), the explainer certificate-question router (identity-resolved, REJECTED answers certificate-only), and one grade-distance triage. Two frozen quality notes lack a resolvable IDS §-cite in `fix_looks_like` — reported for a design-thread note_version fix, quarantined not edited. Errand (a): the WIP progressless-in-progress disposition is `EXCLUDED`, not `DEFAULTED` (no progress invented). With this, **all Phase 2 workstreams are complete** (cloud in-cloud confirmation still carried from 2.4).
**v1.5:** remediation catalog re-based on the docs/06 §4 Rule Registry (curated note per gate rule, finding-code fallback for rule-less findings) — the Certificate groundwork (registry, gate completion, evidence-shape) landed 2026-07-10.
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
- **Cloud deployment, encrypted**: TLS in transit, encryption at rest, secrets management. Single tenant by construction (one pilot); tenant isolation as architectural rule for tenant #2. **No certification this window** — trigger: pilot converts to paid or prospect #2 requires attestation; then Type I → Type II. ✅ DONE 2026-07-14 (session 2.4) — multi-stage Dockerfile (non-root, pinned lockfiles, `/health`, image-as-shipped CI) + compose parity; TLS-terminating Caddy overlay (`tls internal`) + encryption-at-rest as a volume/disk property + secrets via env injection only + CI secret-scan (gitleaks); **docs/08-security-posture.md** (W4 posture note: what's encrypted/where, key custody, single-tenant-by-construction with the named tenant-#2 isolation trigger); Azure Container Apps deploy artifacts in `deploy/azure/` (Bicep + deploy.sh + provider-swap-boundary README) with managed TLS, platform secrets, encrypted Azure Files `/data`; provider-agnostic app/image by construction. **Carried gap:** deploy-verified-LOCALLY, not in-cloud — no live Azure subscription this session (Bicep unvalidated vs ARM, image not built [no Docker], smoke ran against a local server). See the docs/04 CU0–CU3 amendments.
- Storage past loose files only where it hurts (run registry, certificate history — SQLite-class). ✅ DONE 2026-07-13 with the API layer — `api/registry.py`: SQLite index (submissions, certificates, runs, schedules); filesystem stores remain the artifact truth. Solver-gap research parked per spike verdict.
- **Conversational Certificate** — the certificate becomes an interrogable surface, not a verdict document; the customer's *first conversation* with the system. Components: (1) a certificate question domain in the explainer router ("why was this rejected?", "what's wrong with my orders file?", "what should I fix first?") reading gate findings already in the evidence store; (2) a **remediation catalog** — a curated, versioned note **per gate rule (docs/06 §4 registry), with a finding-code fallback note** for findings that resolve to no rule (what the check means, typical causes, what a fix looks like, citing the IDS section that defines the rule) so fix-advice is authored knowledge rendered per-case, never LLM improvisation; (3) register mapping — what's-wrong = testimony (findings, evidence, footnotes), how-to-fix = remediation register (authored guidance, spec-cited), what-matters/triage = judgment grounded in severities and counts. **Jurisdiction rule:** remediation coaches toward the IDS requirement, never toward ERP-specific surgery — the spec is ours, their ERP is theirs. Truth manifests for CONDITIONAL/REJECTED scenarios gain expected-remediation assertions.
- **WIP / soft-start rescheduling (IDS v0.3 §5.13):** `wip_status.csv` doorway + gate coherence checks; adapter lands observed state on WorkPackage.state; solver treats complete ops as satisfied, in_progress ops as fixed intervals for remaining duration, and honors the **amended invariant** (no *newly scheduled* start before reference_date; observed in-flight starts exempt) at both clamp sites. Generator scenario **mid_replan** (truth manifest: fixed ops stay put, completed ops free capacity, only the future moves) ships with it per W1. Recurring pilot submissions ARE rescheduling — a live plant's second submission contains WIP or the schedule is fiction. ✅ DONE 2026-07-14 (session 2.3) — `WipStatus`/`WipOperationObservation` contracts + `Demand.wip_operations`/`Operation` WIP fields (docs/01 §5.1/§5.2/§5.4); gate doorway + manifest declaration + five coherence checks as findings (add-never-repurpose); IDS adapter lands observations with truthful observed provenance citing source rows; Planner projects onto Operations + WorkPackage.state; solver removes complete ops (capacity freed), fixes in-flight ops on the observed resource (busy span carved out of calendar blocking), amended invariant at both clamp sites; Validator TEMPORAL_IMPOSSIBILITY exempts in-flight (ghost-job fix un-regressed); mid_replan scenario with capacity counterfactual + warm-start proof. See the docs/04 amendments.

**Exit demo:** 3,000-order generated submission → schedule via API in minutes, repeatably; scale-ladder timings as regression baselines. ✅ DEMONSTRATED LOCALLY 2026-07-14 (session 2.4, `deploy/smoke.py`): clean_large ~3K orders → ACCEPTED/C1 → 7,460-assignment schedule via the API → one what-if, ~165s total (deterministic); baselines in `deploy/scale_ladder.json`. Over the containerized/cloud stack it re-runs unchanged (same `--base-url` script) — the in-cloud run is the carried confirmation.

**✅ PHASE 2 EXIT — AUDITED & COMPLETE (qualified), 2026-07-10.** A fresh audit session ran the exit prompt's five clauses live (Clause 6 addenda resolved at `acb75b8`): exit demo repeatably byte-identical across two fresh API runs (7460 assignments); every Phase-2 item live-verified (API 409/listing invariants; warm-start 0-vs-51-move noise case; pool diversity@15min + snapshot byte-identity + supersede-invalidation; mid_replan WIP counterfactual + sunk-setup ledger; the three certificate registers with §-cited remediation and the jurisdiction rule); the gauntlet reproduced its golden byte-identically with the **173-exclusion** anchor (run under the default `identity_v1`, 0 merges). **No clause failed; the audit was fix-free.** Carried exit qualifications: (1) cloud **in-cloud** confirmations — in-container CI + live `az deployment` + cloud smoke — OPEN, → follow-up **2.4b** (Docker/Azure unavailable at audit); (2) the raw_data path bypasses the M0 gate / has no WIP doorway — Phase-4 (pilot connector); (3) pool slice-awareness + warming-on-publish — parked to Phase 3; (4) two quarantined catalog notes lack an IDS §-cite — design-thread note_version fix; (5) W1 scenarios `dwell_heavy`/`calendar_chaos`/`multi_facility_balance`, the sentinel-value detector, the provenance spot-check guard, and `yield_factor` false-observed provenance — OPEN, re-parked (W1/Phase 3). See the docs/04 2026-07-10 exit-audit amendment. **Entering Phase 3.**

### Phase 3 — The reasoning cockpit (weeks ~8–16, center of gravity)
Not "a Gantt with chat" — **one reasoning surface, three input modes (gesture, language, voice)**, all front-ends to the same machinery (canonical model, evidence, scenario runner, solution pool), sharing session state: same schedule version, same sandbox scenario, same selection.

**Interim-A status (2026-07-11, v2.0→v2.1):** ✅ CU1 `multi_route` scenario · ✅ CU2 contract 1.2 interaction payload · ✅ **CU3 cockpit shell** (`src/cockpit/`, read-only vis-timeline board of a live contract-1.2 document) · ✅ **CU4 ask panel** (M10 embedded, register-distinct, cited-bar highlighting, deictic selection) · ✅ **CU5 screenshot harness** (`tests/cockpit/`, 6 states + C1 drift + mid-pan, headless CI). Acceptance driven live. **Language mode + read-only board are in; gesture (drag, Tier-0/1/2) and voice are interim-B and later.**

**Three-tier drag-and-drop:**
- *Tier 0 — legal zones (instant, no solver):* on grab, pure canonical arithmetic shades the board — green (fits), amber (fits, displaces), dim (illegal: capability/calendar/precedence). Computed client-side from the schedule JSON.
- *Tier 1 — priced ghost slots:* overlay the task's positions in other complete schedules, each labeled with its known objective delta ("+$120: Tue 09:00 on the other press"). **Two ghost sources, unified rendering — RESOLVED 2026-07-12 → R-T1a/R-T1b** (docs/04 2026-07-12 amendment): (1) POOL members (near-optimal, the cheap options) and (2) FORCED-ALTERNATIVE solves (per-op re-solves each carrying a "not on the incumbent machine" cut, warm-started, short time limit) — the latter gives the TRUE best price of each road not taken, an infeasible forced solve rendering as a proven "not feasible this horizon" verdict, so every eligible machine wears a price or a verdict. This closes the 3.1 multi_route finding that pool-only ghosts degrade on economically realistic (distinct-rate) data. Forced solves run async post-publish per likely-grabbed op, stored as pool-member-class documents, invalidated on supersede (R-T1b); they multiply pool-build solve count and inherit the pool's slice-awareness qualification. Demo language: "priced alternatives," not "near-optimal alternatives." Pre-priced, coherent placements, zero drag-time computation.
- *Tier 2 — the drop:* compiles to a **pin constraint** (never mutation), re-solves in the what-if sandbox, actual delta shown for accept/reject; accepted edits are Decisions with authority; publish workflow proposed → published. **Sandbox time-boxing — RESOLVED 2026-07-12 → R-T1c** (elaborates R-DP2; docs/04 2026-07-12 amendment): the re-solve runs under a hard, visible budget (design token, initial 15s) with three honest outcomes — verdict within budget → delta card; feasible-but-bound-unproven → card ships flagged ("≈ delta, bound not proven"); nothing within budget → R-DP2 return-home. The board is never blocked; drops onto a ghost may render from the vouching schedule near-instantly. CI: a pinned re-solve on the demo fixture must return a verdict within budget (a standing latency regression).
- Drop-pin ruling **RESOLVED 2026-07-11 → R-DP1–R-DP7** (docs/04 2026-07-11 amendment): the pin is **both (machine + time), literally as displayed** (R-DP1); commit-or-return with mid-drag refusal of illegal zones (R-DP2); semantic snap in legal zones (R-DP3); gesture=command / language=wish, soft preferences as objective penalty terms (R-DP4); HOLD/DEFER verbs (R-DP5); legality epistemics per layer (R-DP6); change legibility — no schedule change renders as a silent swap (R-DP7). This is the cockpit edit vocabulary; drag-intent inference as primary mechanism is superseded.
- Frontend: **substrate SELECTED — vis-timeline** (MIT/Apache-2.0), decided by the Session 3.0 + 3.0b bake-off (`tools/spikes/frontend_bakeoff/`, throwaway spike; evidence in `VERDICT.md`). 3.0b held vis-timeline to the drop ruling's four killer criteria and it cleared **all four clean** on machine-checked evidence: (C1) an always-on overlay layer carries the priced ghost labels + tentative hatch and tracks vis's pan/zoom at **0 px drift** across zoom levels — fixing the 3.0 in-bar label clipping; (C2) illegal (dim) rows **visibly refuse the drop mid-drag** (bar pins at the legal boundary, not-allowed cursor + banner) and return home on release; (C3) one real magnet through `onMoving` — clean monotonic falloff to a single anchor, Alt-disable, and vis fires the hook **per pointer-move (no throttle, 0.95 call:step)**; (C4) **20/20** headless drag runs. Custom React/SVG+dnd-kit remains the zero-blocker fallback. Commercial upgrade (Bryntum-class, OEM licensing) a later decision. Carry-forward: the overlay reads vis DOM geometry (stable public-ish surface) and the headless harness needs the diagonal group-crossing engage gesture — both documented, neither a failure under evidence.
- Interaction-payload delivery **RESOLVED 2026-07-12 → R-T1d** (docs/04 2026-07-12 amendment), **BUILT in Session 3.2a CU1**: contract 1.2's `interaction` block moved to the split endpoint `GET /schedules/{id}/interaction` (the +35.7% Tier-0 payload measured in 3.1 CU2) at contract **1.3**, fetched on schedule load in the background after first paint — never grab-triggered (a network round-trip must not sit inside Tier-0's latency budget); stale-while-revalidate on schedule-version change. The board renders read-only immediately; drag affordances enable (a stub flag in 3.2a) when the payload arrives. Closes the "split-endpoint proposed, not implemented" note carried since CU2.
- **Interim-B part 1 (Session 3.2a, the cursor-free data spine) — COMPLETE 2026-07-12:** the split endpoint (CU1, above), the client-side **Tier-0 legality library** (CU2 — `src/cockpit/legality/tier0.js`, the arithmetic behind the green/amber/dim shading, tested headless), the **forced-alternative service** (CU3 — the Tier-1 priced ghosts from R-T1a, `forced_alternatives.py`, `POST/GET /schedules/{id}/alternatives`), and the **sandbox latency budget** (CU4 — R-T1c's three-outcome classifier + pinned re-solve, `sandbox.py`). The gesture surface that consumes them (grab/shade, ghost rendering, magnets, the Tier-2 drop, R-DP7 change traces) and voice are **Session 3.2b and later**. See the docs/04 2026-07-12 Session 3.2a amendment.
- **Interim-B part 2 (Session 3.2b, the gesture surface) — COMPLETE 2026-07-12, and with it interim B:** ✅ CU1 grab → Tier-0 shading (`drag/shade.js`, grab→shade < 100 ms) · ✅ CU2 ghosts (`drag/ghosts.js`, unified/priced/tracking) · ✅ CU3 drag physics (`drag/magnets.js`, semantic snap + Alt-disable + dim-refuse + return-home) · ✅ CU4 drop → tentative → verdict (`drag/controller.js`+`drag/sandboxui.js`, `POST /schedules/{id}/sandbox`, three honest outcomes, accept stubbed-disabled) · ✅ CU5 change traces (`drag/traces.js`, moved-set old→new, card lines linked to bars) · ✅ CU6 dev-only feel tuning panel (`drag/tuning.js`, hot reload + export). Rendered against `multi_route_distinct`; backend spine additive (sandbox moved-set + `/sandbox`, forced-alternative `alternative_placement`, distinct cockpit fixture); cockpit JS **23/23**, Python **1026**. **Still out:** the accept/publish path (final) and voice (later interim). See the docs/04 2026-07-12 Session 3.2b amendment. **(3.2c, 2026-07-14: the drag/pan conflict found live on `busy_board` and fixed — real-pointer drags no longer pan the board; cockpit JS 24/24. See v2.4 above.)** **(3.2d, 2026-07-14: six feel-session fixes from a live `busy_board` run — shading clears on drop (CU1), Accept reads disabled (CU2), the deictic seam injects the resolved selection (CU3), the fallback menu speaks planner (CU4), shading-emphasis knobs added (CU5), the fail-closed LLM renderer wired for dev (CU6); cockpit JS 26/26. See v2.5 above.)** **(3.3, 2026-07-14: Tier-1 coverage + card explainability — the forced-alternative heuristic widened + an on-demand-on-grab path pricing every eligible machine (K'), the empty ghost `work_orders` fixed, the delta card's major consequences gain an occupancy "why" line, drop-onto-ghost traces the full moved-set, feel-fixture test guards + sandbox applied-time-limit echoed; cockpit JS 30/30. See v2.6 above.)** **(3.3b, 2026-07-15: the standing "ortools 9.15 vs golden baseline" reds were a wall-clock time-bomb, not solver drift — the manifest-less sample_data path validated against `datetime.now()`, so once the clock passed WO-2001's 2026-07-13 due date the demand was excluded and the golden diverged. 9.15.6755 reproduces every golden byte-for-byte; pinned exact + a `test_ortools_pin.py` drift guard; sample epoch pinned to 2026-07-09 via a new `--reference-date` flag; goldens STAND, no regeneration; generator/cockpit/feel fixtures confirmed epoch 2026-01-05 and unaffected. Full suite green (1033 non-slow + scenario slow ladder). See the docs/04 2026-07-15 amendment.)** **(3.4, 2026-07-15: the interim FINAL — accept→Decision→publish (the base is never mutated; publish supersedes + invalidates pools), the sandbox/edit question domain ("summarize my changes" + decomposed cost delta over the planner_edit Decisions), voice (push-to-talk into the same ask path, register aloud, record ids never voiced), ghost latency (pointer-down pricing + parallel K-solves), and the sixty-second rehearsal driven end to end beat by beat. Cockpit JS 34/34; Python 1035 non-slow. Phase-3 build COMPLETE, awaiting exit audit. See v2.7 above.)**

**Conversational layer on the same surface:** answers highlight bars as they cite them; "what are my options?" glows the same Tier-1 ghosts; drags are narratable ("summarize what I changed today and what it cost" → sourced session narrative, since edits are Decisions). Pool-consensus becomes new testimony ("in 4 of 5 near-optimal schedules this runs on WC-B"). All honesty armor intact: registers never blend; testimony validates against bundles; judgment names its records.

**Voice:** push-to-talk speech-to-text into the same answer() (Web Speech / Whisper-class); spoken responses give the summary sentence and the register aloud ("My take:") while **the screen holds the receipts** — record IDs are never read aloud; ears for the answer, eyes for the footnotes.

**The demo script (exit bar, and the website's centerpiece):** planner asks *why is the Henderson order late* (voice) → sourced answer, bars highlight → *what are my options* → three priced ghosts glow → drag onto one → delta confirms → publish → *summarize my changes* → sourced narrative. Sixty seconds; every number traceable. **BUILT + REHEARSED end to end (Session 3.4, v2.7):** the whole arc runs beat by beat in `tests/cockpit/rehearsal.spec.mjs` (screenshot-asserted, per-beat latency recorded to `shots/rehearsal_report.json`) — ask why (voice) → 3 bars glow · grab → priced ghosts · drag onto a ghost → verdict + traced moved-set · **Accept → a new proposed version → Publish supersedes the base, the strip flips** · "summarize my changes" (voice) → a narrative naming the edit + its authority. Hermetic (the fixture server stands in for the API across the arc); the REAL accept→Decision→publish + the REAL decomposed edit-domain answer are proven against the live API by the Python tests (`test_planner_edit`, `test_edit_question_domain`). **Phase-3 build work is complete; the exit demo now awaits a fresh audit session driving it cold.**

**Website (first-class, the demo's home):** positioning from the niche statement; the certificate story upgraded to its interactive form — **upload a sample, get your certificate, ask it questions** (a prospect interrogating their own data's report card in a browser, before anyone signs anything); the cockpit footage; demo access. Kickass, thin, honest.

**Exit demo:** a stranger who plans for a living drives the script cold, no terminal.

**✅ PHASE 3 EXIT — AUDITED & COMPLETE (qualified), 2026-07-15.** A fresh audit session ran the six exit clauses LIVE against the real dev stack (uvicorn + `busy_board`, deterministic). **One seam found + fixed in-session** — the delta card showed the scaled solver objective as dollars (~120× the ledger cost delta); fixed to show ledger dollars (`cost_delta_abs`, decomposing exactly) and re-verified live. The sixty-second script ran end to end twice (deterministic legs agree; accept→Decision→publish→supersede→pool-invalidation→summarize all live-verified); R-DP compliance via the harness; latency baselines recorded (first-grab ghosts 6.2s, cached 3.6ms, sandbox 15s=budget→flagged, grab→shade 5.2ms). **1036 non-slow Python passed (0 failed) + cockpit 34/34.** **Carried qualifications → Phase 4 entry conditions:** (1) the **cold-stranger drive** is MET-BY-PROXY only (Daryn's feel sessions + this audit's live runs + the hermetic rehearsal) — the actual non-developer cold-drive is a NAMED Phase-4 entry condition, not relaxed; (2) cloud in-cloud confirmations (2.4b) still OPEN; (3) Daryn's feel-token export not yet committed (runs on `DEFAULT_FEEL`); (4) slice-awareness, LLM voice normalizer, ghost precompute dial (a), pool-ghost partial consequences, real auth — re-parked. See the docs/04 2026-07-15 Phase 3 exit-audit amendment. **Entering Phase 4 preparation.**

### Phase 4 — Pilot (target: live by month ~5)
The ticketing client. Entry conditions (the no-half-baked rule): Phase 1 exit passes **on their data** without accommodation; a non-developer drives the cockpit cold; their live extract gates CONDITIONAL or better. No promises before conditions are met. Their connector, recurring IDS submissions, certificates trending, schedules published in their vocabulary via the identity map. **Exit:** their planner uses it in anger for a month; the certificate/quality trend line is the case study.

## 4. Post-pilot sequence (named, ordered)

1. **ATP/CTP** — the natural prospect question, mechanism already built: a what-if scenario with a hypothetical Demand injected; answers are promise dates *with priced alternatives* ("April 14 normal; April 9 with overtime at $X; April 7 if order Y slips at $Z"), evidence-traced — askable by voice mid-phone-call. Needs: fast/incremental re-solve (Phase 2's pool work is the head start), a `quote_request` IDS doorway, promise-becomes-firm-Demand (locks generalized). Killer feature for prospect #2.
2. **MES horizon** — actuals as observed entities, planned-vs-actual evidence, schedule-stability objective, advisory maturing to trend-backed counsel, multi-user/auth hardening. Scoped from what the pilot teaches.
3. **Certification** — on its trigger (paid conversion or prospect requirement): SOC 2 Type I, then Type II on its long evidence clock. Encryption now; attestation when commerce demands.

## 5. Cross-cutting workstreams

**W1 — Scenario & Anomaly Catalog (the gym, permanently open).** No capability is done without its generator scenario and truth assertions (docs/06 §8). Stage exits run on generated scenarios; reality is reserved for pilots.

**W2 — Documentation & Rulings.** docs/05; the remaining open rulings (queue §6 — drop-pin RESOLVED 2026-07-11 → R-DP1–R-DP7, docs/04 amendment); docs/04 amendments same-commit; CLAUDE.md status current at every session end. **CLAUDE.md carries position, qualifications and carry-forwards ONLY** (2026-07-25, session CE1): session close-outs are written to docs/04 and docs/07, never narrated in CLAUDE.md, and CLAUDE.md is checked against a **40k-char ceiling at every phase exit** — it reached 191,692 bytes against Claude Code's 150k delivery limit before extraction, 94% of it a changelog duplicating docs/04.

**W3 — Go-to-Market surface (real in Phase 3).** The website, the demo script as repeatable asset, the certificate-as-sales-artifact motion, capability matrix = docs/05 with test-status.

**W4 — Security & Compliance.** Encryption + secrets from first cloud deploy; tenant isolation architectural from tenant #2; audit story half-built by the evidence contract; certification on its trigger, post-window.

## 5a. Carry-forwards owned here (named debts, not close-out prose)

A debt named only in a session close-out does not exist. These are owned and
re-read when the area is next touched; CLAUDE.md carries the short list, this is
where the reasoning lives.

1. **`--horizon-days` files horizon work as EXCLUSION** (found by a Session 4B.6
   pre-flight, not fixed there — out of scope, naming it was the deliverable).
   `src/mre/__main__.py` (251-300) adds every demand due beyond
   `reference_date + N days` to `ValidationResult.excluded_demand_ids` — the same
   set that carries GATE exclusions, i.e. data defects. It is a **production
   path**, reachable through the API (`SolveRequest.horizon_days` →
   `app.py:854`); `scenario.py:278-293` only reproduces it for what-if parity.
   What it removes is exactly the population the coarse zone exists to price, so
   it is **a horizon category shelved as a data-defect category**. It is not
   silent (a MODEL_SIMPLIFICATION / POLICY_RULE Decision records the deferred
   count), but the shelf is wrong: a demand deferred by a planning horizon is not
   a demand we could not read. **NOT reachable from a rolling run** — the rolling
   worker never passes it — so the coarse zone is not starved by it today.
   *Fix shape:* a distinct `deferred_demand_ids` set with its own disposition, so
   the completeness invariant can tell "beyond our horizon" from "we could not
   use it". Blocked on nothing; sequenced behind the RawAdapter retirement, which
   touches the same entry points.

   **RAISED 2026-07-28 (Session 4B.11): THIS IS NOW A NAMED RULING VIOLATION, not
   just an untidy category.** R-PD1 clause (2) rules that exclusion is a
   DATA-DEFECT category only and can never be applied to a true statement about
   the plant's position — *late, beyond horizon, over capacity*. "Beyond our
   horizon" is exactly such a statement, so this path violates the same clause the
   past-due finding did, and does so on a **production** entry point. It is also a
   clause (3) violation, and a worse one: `scenario.py:280-293` raises **no finding
   of any kind**, so nothing names the module that removed the demand or the reason
   — the general guard committed in `tests/test_pastdue_disposition.py` would catch
   it if applied to that path. Untouched in 4B.11 (out of scope; the fix is a
   category change on a production path), but it is no longer a matter of taste.
2. **Per-component gravity ablation** (4B.2c, restated here because Session 4B.6
   built a mechanism ADJACENT to gravity and an unproven component must not be
   invisible while we do). `test_gravity_counterfactual` proves the BUNDLE — all
   three pulls on vs all off. **No INDIVIDUAL component is proven, and
   setup-family affinity is the priced-air candidate** (it may contribute nothing
   on its own). Also recorded in docs/04's 4B.2c amendment; now in CLAUDE.md's
   carry-forwards, where it was missing.
3. **The coarse-to-gravity UNLOCK CONDITION** (R-SC2 coarse-zone amendment clause
   4). Coarse output must not reach gravity's criticality read or the window
   build. Enforced today as an import-direction test. **Revisit only once the
   conformance report (CU3's store) shows coarse bucket-tardiness is calibrated**
   — stated in advance so a future coupling is a decision, not a drift.
4. **The three deferred coarse refinements**, gated on CU3's data: family-presence
   setup in the coarse model; **cross-bucket allocation for resumables** (today
   resumable ops are EXCLUDED and named, because single-bucket forcing would
   TIGHTEN the relaxation and break clause (1) — the exclusion is what makes the
   clause true); and the per-WorkPackage makespan bound. Each is a TIGHTENING, so
   each must be landed against the CU4 relaxation guard.
5. **The coarse zone is UNEXERCISED at demo density.** On the 40-order
   pilot_scale plant the beyond-horizon set is real (38 demands, 83 ops) but the
   load is ~8% of derated capacity: no cell binds and coarse tardiness is 0. The
   teeth at that size come from the clause-(2) and non-monotonicity tests.
   **PARTIALLY DISCHARGED (4B.6a CU3):** `tests/test_coarse_binding.py` now pins
   the binding behaviour at 200 orders — 404 ops modeled, peak utilization 0.998,
   9 binding cells, 123 buckets of tardiness, rho 0.5 INFEASIBLE with the op
   population unchanged. The DEMO instance is still light (same root as the 4B.2c
   CU5 finding), but the model's binding behaviour is no longer unregressed.
6. **Coarse slip attribution is mostly `unattributed`.** A confident attribution
   needs the FINE solve's binding constraints, which the prediction store does not
   carry. The report states this about itself rather than guessing a cause. The
   store now HAS data to attribute over (4B.6a CU1), so this is next-actionable
   rather than blocked.
7. **The absent `ANTHROPIC_API_KEY` blocks MORE than the exam bank — four
    committed SLOW tests fail on it too** (4B.7, newly observed and verified
    against HEAD before the session's own changes, so it is pre-existing and
    unrelated to them). `test_api_endpoints.py::TestRollingTwoBeatAPI::
    test_rolling_questions_answer_through_ask` and the three
    `test_edit_question_domain.py::TestEditDomainEndToEnd` cases all land on the
    honest could-not-interpret floor ("I can't answer this question yet"),
    because since 4A.5a EVERY question is parsed by a MODEL against the closed
    intent vocabulary and **no deterministic classifier survives anywhere** — by
    design. Without a key there is no parser, so the floor is the correct
    behaviour and the tests are asserting a capability the environment cannot
    provide. **This is a TEST-SUITE HONESTY problem, not a code defect:** a full
    `--runslow` run is red for a reason that has nothing to do with the change
    under test, which is exactly how a real regression gets waved through. *Fix
    shape:* mark them `skipif` on the key's absence with the reason stated, so
    "4 failed" becomes "4 skipped: needs ANTHROPIC_API_KEY" — NOT to be confused
    with weakening them. Recorded, not fixed: it is a suite-wide decision.
    **RESOLVED 2026-07-28 (Session 4B.8 pre-flight) — and it was never the
    key.** `.env.local` was present and valid at the repo root the whole time;
    **nothing on the test path loaded it.** `tests/conftest.py` registered
    `--runslow` and nothing else, while `tools/run_ai_exam_sweep.py:42` carried
    the repo's ONLY loader — which is why the exam harness saw a key and pytest
    never did. The `anthropic` SDK was importable throughout (0.118.0), so that
    was not it either. The loader is now in `tests/conftest.py` (repo-root
    anchored, already-set variables win; `python-dotenv` is not a dependency, so
    it is hand-rolled exactly as the exam harness does it). **The four tests pass
    in 40.6 s.** No `skipif` was added and no assertion weakened — the fix shape
    named above turned out to be treating the symptom.
    **A NEW consequence, reported not absorbed:** four OTHER tests had been
    passing only because the key was AMBIENTLY ABSENT
    (`test_llm_renderer_no_key_attribution`,
    `test_judgment_no_llm_falls_back_to_testimony`,
    `test_the_preflight_is_fail_open`,
    `test_an_unavailable_synthesizer_returns_none`). Each now CONTROLS the key
    with `monkeypatch.delenv`; no assertion changed. One was not merely failing
    but making a LIVE API CALL and asserting the fallback register on a real LLM
    answer. **STILL OPEN, a suite-wide call:** `LLMRenderer`, `Synthesizer` and
    `QuestionParser` all spell the key `api_key or os.environ.get(...)`, so an
    EXPLICIT `api_key=""` silently consults the environment. `api_key=""` plainly
    means "no key". ~20 further `LLMRenderer(api_key="")` sites in
    `test_explainer.py` now build AVAILABLE renderers; they pass today because
    they only build prompts. Making an explicit empty string mean what it says is
    a behaviour change, deliberately not made here.
    **`regression_founder_r5` was NOT run** (this session's out-of-scope list) and
    its expectations were NOT recalibrated. The blocker is now removed, so the
    next session can run it — see §5a.22 for what must be re-derived first.
    Below, the original entry:
    **`regression_founder_r5` is UNRUN AFTER FOUR SESSIONS** (committed 4B.5, unrun
   through 4B.6 and 4B.6a). Its 27 graded expectations have never been graded —
   including the 4B.6a question that is the only check that the ASK PANEL voices
   the delta card's MOVE part rather than the total. **Blocked on one thing: no
   `ANTHROPIC_API_KEY` in the working environment.** Without it the runner builds
   neither a parser nor a synthesizer, so every question lands on the honest
   could-not-interpret floor and the "grade" would measure the absence of a key.
   Not skipped, not marked delivered: unrun.

    **CLOSED 2026-07-29 (Errand 4B.16a) — AND THIS ENTRY IS THE THING THAT WENT
    WRONG.** §5a.7 has now misled THREE TIMES: six sessions of "the r5 bank is
    key-blocked"; 4B.15 finding the exam harness had always had its own loader;
    and 4B.16 citing it a third time to explain why its two new routes were left
    unmeasured against a live parse. Every session that read this line scoped
    itself wrongly from it. What was true, stated once and plainly:

    * **THE SWEEP TOOL WAS NEVER BLOCKED.** `tools/run_ai_exam_sweep.py` has
      carried its own repo-root-anchored loader since **4A.5b** (commit
      `f3bb319`, 2026-07-26) — it predates every claim above that the bank could
      not be run. Errand 4B.16a ran it live from its own entry point: parser
      available, one live parse, **1319 ms**, graded 1/1. `regression_founder_r5`
      was never gated on a key. Its real blocker is **§5a.22** — the bank's
      expectations have never been calibrated and the exam world has moved
      under them again — which is a session's work, not an environment fault.
    * **PYTEST WAS BLOCKED, FOR ONE SESSION.** 4B.7 observed it, 4B.8 fixed it by
      copying the loader into `tests/conftest.py`. Re-verified this errand: the
      four named slow tests pass, **4 passed in 54.7 s**.
    * **TWO ENTRY POINTS WERE BLOCKED AND NOBODY LOOKED.** `python -m mre.ask`
      and `python -m mre.ai_exam` — the harness's own module front door — had NO
      loader at all, so from a bare shell they built an unavailable parser and
      answered on the honest could-not-interpret floor. That is
      indistinguishable from a missing key, and it is the reading that kept this
      entry alive. Fixed here; `python -m mre.ai_exam` now reports `llm mode
      live`.
    * **THE MECHANISM WAS NEVER THE KEY AND NEVER ONE READER.** Nothing in the
      library loads a file — `question_parser`, `renderers`, `synthesizer` and
      `api/app` all read a bare `os.environ`, which is correct, because in a
      container the key arrives from the platform secret store. So every ENTRY
      POINT must populate the environment itself, and the repo had **four
      independent implementations** of that step (`dev_api.ps1` in PowerShell,
      the sweep tool, `conftest.py`, and a spike copy that had already DRIFTED to
      `os.environ.setdefault`, which writes an EMPTY value where the other three
      skip it) plus the two front doors with none. **`src/mre/env_local.py` is now
      the ONE reader**; `tests/test_env_local_one_reader.py` fails on the
      appearance of a second one and has a proven negative control.
    * **REMAINING TRUTH: none about the key.** The two live carry-forwards in this
      entry are unrelated to it — `api_key=""` silently consulting the
      environment (a behaviour change, unmade), and §5a.22's uncalibrated r5
      expectations.

    **The lesson is about the register, not the bug.** This entry said "blocked on
    one thing: no `ANTHROPIC_API_KEY`" and then kept saying it after the sentence
    stopped being true, because a carry-forward is read as a finding and nobody
    re-tests a finding. A blocker claim must name the CHECK that would falsify it
    — here, one command and one printed `parser available=` line.

8. **`record_roll_history`'s data-root sweep is a CORRECTNESS debt, not a
   performance one** (re-filed 4B.6b item 4; was filed at 4B.6a CU1 as O(runs)).
   `sweep_data_root` is `root.rglob("coarse_predictions.jsonl")` with exactly one
   filter — `p.run_id != run_id` (`coarse_predictions.py:169-178`, `:360`). It is
   scoped by **nothing**: not submission, not plant, not facility. A realization
   then matches on **`op_id` alone** (`placed.get(pred.op_id)`, `:230`); nothing
   else is compared before the row is written — not the demand, not the plant,
   not the bucket grid. Because `Operation = f(order_id, route_id, product_id,
   sequence)` carries no plant term (§5a.13's derivation), two sites of one
   company on one ERP catalogue collide by construction.
   **MEASURED:** two plants, same scenario catalogue, different seed (different
   order book), one data root — plant P solved first (5-day window, 174
   predictions), plant Q second (45-day window, 96 ops placed). Q's roll wrote
   **20 realizations against P's predictions**. Demand-id overlap 40/40,
   operation-id overlap 10, resource-id overlap 15/15. The rows are nonsense on
   their face (`predicted_bucket 1 → realized_bucket −1`, a "realized resource"
   from the other plant) and they land in the conformance report's
   `realized_fraction`, slip census and gravity-disagreement count.
   Harmless in a single-tenant demo root; wrong the first day a pilot root holds
   two plants. **NOT FIXED HERE** — the fix is a scope key on the store plus a
   decision about what plant identity IS in the canonical model (the manifest's
   `facility_scope` is the only candidate and nothing downstream reads it).
   The performance reading still stands on top of it: every prediction ever
   written, including the permanently-orphaned ones in §5a.13, is re-swept on
   every subsequent rolling solve forever.
9. **DISCHARGED (4B.7 item 5).** The fixture's window incumbent was ~7.9%
   dearer than the one it replaced (26,507.78 -> 28,597.23) — an incumbent of a
   FEASIBLE search whose identity moved with the 2026-07-26 variable-ordering
   fixes. It is no longer an incumbent of anything: with the earliness price out
   of the objective the regenerated board sits at **16,481.95 with tardiness
   0.00**, which the A0/A0s arms independently prove OPTIMAL on 5/5 seeds with
   seed spread **exactly 0.00**. The 4B.6b explanation of why the ledger wobbled
   with budget (it was not what the window solve minimized) is what closed it.
   The demo board did change again, once, under authorization, with every figure
   accounted by operation identity — docs/04's 2026-07-27 amendment, item 5.
10. **DISCHARGED (4B.6b item 3).** `tools/build_rolling_exam_run.py` builds a
    coarse zone for the harness fixture (failing the build on a wall-truncated
    coarse run, and on a document that comes back without a zone) and sends
    `"coarse": true` plus an explicit `"reference_date"` on the registered solve.
    Verified: the exam world's `document.json` carries a contract-1.9
    `coarse_zone` with all 14 tray items coarsely placed.
    **RESIDUE, named:** the pinned submission under `_ai_exam_scratch/` predates
    the generator's `refinements.coarse_horizon` block, so the exam world runs at
    **rho 1.0, provenance `defaulted`** — 10 density cells, 0 binding, 0
    tardiness buckets. That is correct behaviour (an undeclared plant is never
    given an invented margin) and it exercises the §5.9 "figures assume full
    utilization" voice, but it grades no BINDING answer. Measured and left: a
    fresh generate at the same seed differs from the pinned submission in exactly
    two bytes-worth of things — the manifest's `extract_timestamp` and the
    cost model's `coarse_horizon` (declared 0.85) — every table byte-identical.
    Since `coarse_horizon` never enters the fine solve (clause 4, import-direction
    test), `--fresh` would give the exam world its declared derate with the fine
    world provably unchanged. Not done here: the world the r5 bank's expectations
    were calibrated against is not this session's to move.
11. **The hot-band fixture is a declared-derate contrivance.**
    `tests/cockpit/fixtures/rolling_coarse_hot/` binds because it DECLARES rho
    0.10, not because the plant is loaded. It buys the density band's
    binding-state screenshot coverage; it does not retire item 5.
    *(4B.6b note: it is also degenerate for any FINE-solve comparison — it is the
    same 40-order plant as `rolling/` with only a different declared coarse
    coefficient, and coarse never constrains fine, so its window solve and its
    sandbox baseline are `rolling/`'s to the cent.)*
12. **DISCHARGED BY CONSTRUCTION (4B.7 item 6), not by relabelling.** With the
    earliness price out of the objective, the window solve and the sandbox
    baseline minimize the SAME expression, so the half has nothing to measure
    and correctly measures nothing: on the regenerated fixture `reopt_delta_abs`
    is **−11,975.83 -> exactly 0.00** and `baseline_total_cost` is
    **16,621.40 -> 16,481.95 = the incumbent, to the cent**. The card still
    splits and still sums (32.20 = 0.00 + 32.20). 4B.6b's own proof predicted the
    number. **The card was NOT relabelled**, and the three fix shapes named below
    are moot. The 4B.5 debt that rode with it — the two-solve baseline never
    extended to forced-alternatives pricing — is untouched and still open. The
    original finding, kept because it is why the fix was safe:
    **`reopt_delta_abs` measures an OBJECTIVE MISMATCH, not window
    re-optimization** (4B.6b item 1; the label is wrong, the arithmetic is not).
    The rolling window solve minimizes `sum(objective_terms) +
    earliness_coeff_scaled · Σ(free op start vars)` (`rolling_horizon.py:150-151`)
    where the coefficient is the plant's DECLARED `refinements.earliness_value`
    (R-SC3; pilot_scale declares 0.05 $/min-of-start). The sandbox baseline is
    built by `SolverBuilder.build`, whose own objective is `sum(objective_terms)`
    alone — there is no earliness term. And the extractor's cost ledger has **no
    earliness line at all**: `earliness_value` is read (`extractor.py:101`) only
    to classify a driver (`:637-639`). So the incumbent spends ledger dollars
    buying early starts at a declared price, the ledger never shows what it
    bought, and a baseline that is not charged for early starts beats it on the
    ledger essentially always.
    **PROVEN, not inferred:** forcing `earliness_value = 0` on the shipped fixture
    plant collapses `reopt_delta` from −11,975.83 to **exactly 0.00** (incumbent
    16,481.95 = baseline 16,481.95, incumbent tardiness 0.00). The identity the
    fixture displays — `baseline == total − tardiness` to the cent — holds on the
    40- and 120-order plants and BREAKS at 200 orders (+405.42, baseline
    tardiness 361.67), so it is a property of light-loaded windows where zero
    tardiness is reachable, not an arithmetic identity.
    **WHAT DOES NOT REOPEN:** the MOVE half. Both the pinned re-solve and the
    baseline run under the builder's earliness-free objective, so
    `move_delta_abs = pinned − baseline` is apples-to-apples, and 4B.5 CU1's
    ruling (judge the planner's move against the baseline, never the stale
    incumbent) stands. **NOT FIXED HERE** — changing what the card measures is a
    working-thread decision, and there are at least three shapes (price earliness
    into the ledger as its own line; build the baseline under the SAME objective
    the window solve used; or relabel the half honestly). Whichever lands, the
    two-solve BASELINE has never been extended to forced-alternatives pricing
    (4B.5 debt) and both should move together.
13. **A completed order's coarse predictions are never RETIRED** (4B.6b item 2).
    Predictions are judged only when a later roll PLACES the predicted op. An
    order that leaves the book — completed and dropped from tomorrow's ERP
    extract — can never be placed again, so its predictions stay
    `prior_predictions_pending` forever, are re-swept on every subsequent solve
    (§5a.8), and are counted as neither hit nor miss. **MEASURED:** across three
    consecutive-day submissions, ORD-000001 minted 4 predictions on day 1 and got
    0 realizations; ORD-000002 minted 8 and got 0; day-1's 164 predictions ended
    116 permanently pending. The conformance report's `realized_fraction` is
    computed over REALIZATIONS only, so an orphan does not bias the ratio — but
    it is silently absent from it, which is exactly what clause (7) ("we publish
    our own error bars") should not tolerate. *Fix shape:* a terminal disposition
    (`unjudgeable_absent`) written when a sweep sees a prediction whose demand is
    no longer in the submitting plant's book — which needs §5a.8's scope key
    first, or it would retire another plant's predictions.
14. **The realization INTAKE PATH label does not discriminate at short windows**
    (4B.6b item 2, observed). `gravity_admitted_demand_ids` is
    `admitted(gravity) − admitted(no gravity)` (`rolling_horizon.py:752-769`),
    and on a 7-day window almost everything admitted is admitted by gravity: all
    **78 of 78** realizations across the three-submission run came back
    `gravity_admission`, none `natural_roll`. The definition is right and the
    label is honest; it just carries no signal at that window length, so clause
    (7)'s "two mechanisms disagreeing" count reads ~100% and means nothing.
    Anything built on that count must state the window length beside it.
15. **The shipped window depth is BUDGET-STARVED at pilot volume** (4B.6c
    item 1, measured). `pilot_scale` at **200 orders with the standing window
    14d / frozen 3d** admits **313 free operations** and the window-0 solve
    returns **UNKNOWN — no feasible solution at all** — on the plain cost-only
    objective at a **6.0** deterministic budget (3 seeds; wall 144 / 195 /
    229 s) *and* at **20.0** (1 seed; wall 509 s). Not a tie-break effect:
    this is the cheapest objective the model has. A 7-day window on the same
    plant (99 free ops) proves OPTIMAL at 27,863.63 with 0 tardiness in
    1.86–4.96 deterministic units, so the fix shape is the window length, not
    the budget — but the knee was last measured at 4B.2 CU4b on a 40-order
    plant, and nothing has re-measured it at pilot density. **NOT FIXED HERE.**
    Whatever `SolveRequest.window_days` a pilot ships with must be justified by
    a curve measured at that plant's volume; 14 days is currently a convention
    inherited from a plant 5× smaller.
    **DIAGNOSED 2026-07-28 (Session 4B.8 CU5) - STILL OPEN; the diagnosis was the
    deliverable and no fix was made.** Four findings, full tables in the docs/04
    2026-07-28 amendment:
    * **THE INSTANCE IS FEASIBLE, so this is NOT an R-SC2 admission defect.** The
      earlier UNKNOWN conflated satisfiability with optimality. Asked properly -
      objective replaced by a constant - a feasible schedule is found in **4.51 s
      wall / 0.082 deterministic units**. Gravity did not admit more work than
      the window can hold. The difficulty is entirely in PROVING, not placing.
    * **BOTH STANDING HYPOTHESES ARE DEAD.** Model BUILD time is **0.05-0.19 s**
      at every depth (the 289 s build was the monolith, not this path), and
      ops-per-machine peaks at **92**, nowhere near the ~850 cliff.
    * **THE CLIFF IS BETWEEN 8 AND 9 DAYS at 200 orders** (123 free ops OPTIMAL
      in 4.03 units; 145 free ops FEASIBLE with a 33% gap). The sharpest fact:
      at 14 days the COST solve returns UNKNOWN - **no solution at all** in 6.0
      units - while satisfiability on the SAME model takes 0.082, a factor of
      **74**. The objective is not just hard to optimize; it makes the model hard
      to find anything in.
    * **THE THRESHOLD IS NOT GENERAL.** At 40 orders every depth proves OPTIMAL
      (worst 0.10 units). The cliff falls between 87 and 115 free ops at 120
      orders but between 123 and 145 at 200 - so **200 orders proves optimality
      at 123 free ops while 120 orders fails at 115**. Neither n_free nor
      ops-per-machine predicts it; what differs is how much total work the same
      13 machines carry. Any window rule keyed to a free-op count would be
      fitted to one plant.
    * **A SECOND CEILING BINDS FIRST, AND IT IS THE WALL** (4B.8, newly
      quantified). At 200 orders / 7 days stage 1 needs **37-120 SECONDS of wall
      clock** to spend its 1.86-4.96 deterministic units (5 seeds), but
      `build_rolling_view`'s default `member_time_limit_s` is **30.0**. So on the
      shipped rolling path the WALL stops the cost proof long before the
      deterministic budget does, and the run is wall-truncated — which by the
      repository's own hard rule is a lottery, not a deterministic result. The
      existing `wall_truncated` flag is doing its job here; what is new is the
      measurement of how far apart the two ceilings are at pilot volume. It is
      also why CU3's status ruling is INVISIBLE at 200 orders: the board reads
      FEASIBLE because nothing was proven, not because the wrong proof is being
      reported. Any window-depth decision must set BOTH ceilings together.
    * **NARROWING IS GRACEFUL, NOT LOSSY — the coarse zone absorbs what the fine
      window stops admitting.** Across w7-w12 at 200 orders the exchange is
      smooth and monotone: beyond-horizon demand falls **157 -> 149 -> 140 ->
      120 -> 107 -> 98** as the window widens, and the coarse zone PLACES that
      work rather than listing it — **404 -> 380 -> 358 -> 310 -> 275 -> 249**
      placements over 59/52/50/42/51/34 cells, with **9/9/7/6/5/4 BINDING
      cells** and tardiness buckets falling 123 -> 36, at the declared rho 0.85
      and 4 `coarse_unmodelable` ops named throughout. The displaced demand stays
      modelled and the zone keeps biting; narrowing trades a fine placement for a
      coarse one, which is the R-SC2 amendment working as ruled.
      **The w=14 row is NOT a continuation of that trend and must not be read as
      one:** beyond-horizon jumps to **200 — every schedulable demand — because
      the fine window returned UNKNOWN and placed NOTHING AT ALL**, and the
      coarse zone then carries the whole book (503 placements, 13 binding cells,
      325 tardiness buckets). That is the zone degrading gracefully under total
      fine failure, which is reassuring; but the discontinuity is the failure
      itself, not a window-depth effect. **At the shipped 14-day convention this
      plant's fine schedule contributes nothing and the board is a coarse
      projection.**
    *Fix shape, unchanged and now evidenced:* the window length is the lever, but
    it must be chosen from a curve measured at the target plant's volume - and
    since narrowing MOVES work into the coarse zone rather than discarding it,
    the coarse zone's behaviour at that depth is part of the acceptance, not an
    afterthought.
16. **DISCHARGED (4B.7 item 2b).** `rolling_horizon._two_stage_solve` now
    rebuilds its `SolveResult` to carry **stage 1's objective with stage 2's
    placements**, copying `solver_builder.solve_two_stage`'s long-standing
    convention rather than inventing one — and stage 1's objective is now
    trivially cost, because cost is all stage 1 minimizes. Re-measured on 4B.6c's
    own hand-built model (cost a constant 300, start forced to 20): monolithic
    **300**, rolling **300** — they agree, where they read 400 and 20 before.
    Visible in the regenerated fixture: the delta card's labelled non-money
    fallback headline read `delta_abs` 1,451,373.0 / `delta_pct` **701.79%** and
    now reads **3,312.0 / 0.2017%**, a genuine cost percentage. Pinned by
    `tests/test_objective_units.py::test_rolling_and_monolithic_record_the_same_cost_objective`.
    The original finding:
    **The ROLLING path records a MINUTE COUNT as its solver objective**
    (4B.6c item 4; a defect, PINNED not fixed).
    `solver_builder.solve_two_stage` deliberately rebuilds its `SolveResult` to
    carry **stage 1's** objective with stage 2's placements
    (`solver_builder.py:409-418`) — the whole point being that "the M6
    `solve_complete` objective the assembler + `_incumbent_objective` read stays
    the COST objective" (docs/04, 4B.4 CU1). `rolling_horizon._two_stage_solve`
    returns the stage-2 `SolveResult` **whole** (`rolling_horizon.py:166-172`),
    and stage 2 minimizes `Σ free-op starts` — so its `.objective` is a sum of
    **start minutes**. `build_rolling_view` writes that value into the M6
    `solve_complete` payload (`:574-576`) and `WindowMetric.objective` carries
    it (`:973`). Every consumer named in `SESSION_CLOSEOUT.md` §6 therefore sees,
    on a rolling board, an "incumbent objective" that is a minute count rather
    than cost in any units — including `sandbox`/`planner_edit`'s
    `delta_abs`/`delta_pct` (the labelled non-money fallback headline) and, once
    the pool becomes slice-aware, its cost bound.
    **MEASURED** on a hand-built model (cost a constant 300, coefficient 5,
    start forced to 20): monolithic records **400**, rolling records **20**.
    Pinned by `tests/test_objective_units.py::test_rolling_two_stage_returns_stage_twos_objective_not_stage_ones`.
    *Fix shape:* return stage 1's objective the way the monolithic twin does —
    one line — but it moves rolling telemetry and every golden that reads it, so
    it is a working-thread call, not a measurement session's.
17. **DISCHARGED (4B.7 item 4b).** The gap was ENTIRELY the earliness term.
    With it gone, `_incumbent_objective` returns a COST objective on both solve
    paths and `add_objective_upper_bound` constrains the same expression, so the
    bound's source and target share units: re-measuring the worked example, a
    stated **5% is 5%** (bound 315 over cost 300), where it was 40%. **No gap
    remains, so there is no second cause to report.** Pinned by
    `test_pool_cost_bound_matches_its_stated_tolerance` and
    `test_pool_bound_source_and_target_share_units`. Unrelated and still open:
    the pool must become **slice-aware** before it serves sliced-mode schedules.
    The original finding:
    **The solution pool's cost bound is looser than its stated tolerance**
    whenever a plant declares a positive `earliness_value` (4B.6c item 4;
    PINNED not fixed). `solution_pool.py:214-218` computes
    `int(incumbent_objective × (1 + tolerance_pct/100))` and hands it to
    `add_objective_upper_bound`, which constrains `Σ var_map.objective_terms`
    (`solver_builder.py:209-215`) — the COST objective alone. But
    `_incumbent_objective` returns the recorded **stage-1** objective, which is
    `cost + earliness_coeff_scaled · Σ starts` (R-SC3). The bound's source and
    the bounded expression are in different units the moment the coefficient is
    positive. **Worked example, pinned as arithmetic in the test:** cost 300,
    recorded objective 400, a stated **5%** tolerance is really **40%**.
    Harmless while every plant declares 0; live for `pilot_scale`, which
    declares 0.05 $/min. Compounds with §5a.16 on the rolling path (the bound
    would be derived from a minute count). *Fix shape:* bound the same
    expression the incumbent figure came from, or record the cost objective
    separately for the pool to read — either way, one decision with §5a.16.
18. **R-SC3(1)'s "always and unconditionally" is not free, and the price is now
    measured** (4B.6c items 1–2; a RULING-LEVEL observation, no ruling moved).
    The two-stage implementation is not the problem and the single-objective
    alternative is worse: candidate B (`BIG · cost + Σ starts`) costs **+69%**
    (40 orders) and **+39%** (200 orders, 7-day window) on the LEDGER against a
    cost-only arm whose seed spread is **exactly zero**, and at 120 and 200
    orders it is *also worse on sum-of-starts* than not having a tiebreak at
    all. The hour-granularity variant matches the optimum exactly at 15 orders
    (and proves it in 0.35 deterministic units) but degrades identically from 40
    orders up. **The mechanism is diagnosed, not guessed:** with zero tardiness
    the cost objective is start-INDEPENDENT (production = duration × rate,
    setup a fixed per-op charge), so the cost-only model is a feasibility
    problem CP-SAT closes using **1.7% of its budget** at 40 orders; any
    start-sum term turns it into a min-Σ-starts optimization it cannot close in
    60× that. Corroborated by the 120-order row, where the cost-only arm is
    itself unable to prove optimality and B's penalty collapses to **inside**
    A0's own 87,783 seed spread. The status quo's own damage is measured on the
    same axis: **+73.20%** (40 orders) and **+97.61%** (120 orders) of ledger
    total, almost all of it tardiness — which extends §5a.12 from the fixture to
    every instance above ~15 orders. **Nothing was changed.** Whether R-SC3's
    floor is worth its price at pilot volume is a ruling decision, and it now
    has numbers under it.
    **RESOLVED 2026-07-27 (Session 4B.7):** the ruling was made on these numbers.
    R-SC3(1)'s FLOOR is kept and is not what costs — the price is R-SC3(2), and
    it is RETIRED. Session 4B.7 measured the arm this one never ran (**A0s**,
    staged cost-only, the floor WITHOUT the price) and found it delivers the
    proven cost optimum to the cent at 5/8/15/40 orders while spending 45.53%
    fewer start-minutes at 40 — so the floor is not merely worth its price, it
    has no price. See the docs/04 2026-07-27 R-SC3 AMENDMENT.

19. **Stage 2's deterministic budget is FIXED, not the remainder — and the
    allocation is backwards** (4B.7 item 1, measured, NOT changed). Stage 2
    receives `_STAGE2_DET_TIME_S = 2.0` regardless of what stage 1 left. At 40
    orders the cost-only stage 1 **proves OPTIMAL in 0.101 of its 4.0
    allocation** and stage 2 then exhausts its whole fixed 2.0 without proving
    the tiebreak optimal — so the window consumes **2.10 of a 6.0 budget** while
    the stage that could use more is the one that is capped, and **3.9 units go
    unused**. At 15 orders it is the same shape (0.106 / 2.000). The fix shape is
    to give stage 2 the REMAINDER of the window's deterministic budget once stage
    1 has proven optimality, which is free — but it moves every rolling golden
    and belongs with §5a.15's window-vs-volume work, not bolted onto a removal.
    **DISCHARGED 2026-07-28 (Session 4B.8 CU1+CU2).** Measured before it was
    changed: three policies over a fixed 6.0 total, 6 instances x 5 seeds. The
    fix shape above was RIGHT IN DIRECTION AND WRONG IN DETAIL — a plain
    remainder (P2) hands stage 2 **ZERO on 5/5 seeds at 120 orders**, because
    stage 1 exhausts the whole budget there without proving anything, which
    silently retires the tiebreak at exactly the plant sizes where a planner sees
    Session 4B.4's founder finding. The shipped policy is **P3**: stage 1 capped
    at the total minus a RESERVE (a 1/12 fraction, so 0.5 of 6.0), stage 2 given
    the remainder, floored at the reserve.
    The second half of the defect turned out to matter more than the first:
    **P1 loses the COST PROOF at 200 orders**, where two of five seeds need 4.542
    and 4.962 units and are capped at 4.0 — ledger 29,385.60 and 35,127.05
    against the optimum of 27,863.63 that P2/P3 prove on 5/5 seeds with a spread
    of exactly zero. Where the tiebreak's extra budget pays it is visible too:
    start-minutes -19.41% at 15 orders and -3.43% at 40, both at an IDENTICAL
    ledger. `_STAGE2_DET_TIME_S` is DELETED from both twins; the parameter was
    RENAMED `det_time` -> `det_total` rather than reinterpreted, because the old
    total was `stage1 + 2.0` and no single multiplier preserved every caller.
    Guards in `tests/test_budget_allocation.py`. Full table: docs/04 2026-07-28.
    NB the predicted golden churn did NOT materialise — the rolling golden's
    digest and every asserted figure are unchanged, and sample_data is
    byte-identical.
20. **`EARLINESS_PREFERENCE` now names a mechanism that no longer exists**
    (4B.7, REPORTED, deliberately not fixed — the largest thing left).
    `extractor.py:637-640` attributes a dearer-than-cheapest eligible placement
    to `DriverCode.EARLINESS_PREFERENCE` whenever `earliness_value > 0`, and
    `vocabularies.py:135-137` documents it as "purchased by the declared
    earliness_value coefficient (R-SC3(2))". **R-SC3(2) is retired; nothing
    purchases anything.** It is not silently lying — the attribution is by PRICE
    RANK with no occupancy check, and 4B.3a CU4b already made every such answer
    HEDGE — but its stated meaning is false, and a plant declaring a positive
    rate will still see the code fire. Correcting it is a **vocabulary-class
    change** (add, never repurpose; docs/02 updated in the same commit) reaching
    `planner_language.py:45,151-157`, `explainer.py:1024,1582`,
    `renderers.py:1486`, four `test_ai_voice` tests, `ai_exam/runner.py:341` and
    the RUBRIC. *Fix shape:* either retire the code (leaving the enum member, per
    the never-repurpose rule) and let those placements fall to
    `CAPACITY_BLOCKED`, or give it a new, TRUE meaning — a dearer-but-earlier
    placement the CAP permitted, which is a different claim and needs its own
    evidence.
    **PARTIALLY ADDRESSED 2026-07-28 (Session 4B.8 CU4) — STILL OPEN.** The
    INTERIM was taken: the extractor no longer EMITS the code. Stopping a driver
    from firing adds no vocabulary and repurposes none, so it is not itself a
    vocabulary-class change. The `earliness_value` parameter is DELETED from
    `_assignment_driver`'s signature (a committed test asserts a caller cannot
    pass it back in) and those placements now fall to `CAPACITY_BLOCKED` — which
    was checked FIRST and is strictly better, because since 4B.5 CU3(a)
    `explainer._capacity_forced_alternatives` reads the SOLVED OCCUPANCY behind
    it and names the eligible machines and what held each, with an honest
    "the occupancy does not attribute it" branch. Under a cost-only objective a
    dearer eligible choice IS capacity, so the fallback states the true cause
    with checkable evidence rather than hedging a false one.
    **WHAT REMAINS OPEN is the vocabulary migration itself:** the `DriverCode`
    member still exists and `vocabularies.py:135-137` + docs/02 §4.2 still
    DOCUMENT it as "purchased by the declared earliness_value coefficient
    (R-SC3(2))" — a description of a retired mechanism. Retiring or re-meaning
    the code remains a reviewed change reaching planner_language, explainer,
    renderers, `ai_exam/runner.py:341`, `test_open_card.py:63` and the RUBRIC.
    The two tests premised on the old behaviour were REPLACED AND REVERSED; the
    declared-but-unread guard was resolved by a dormant-register entry citing the
    R-SC3 amendment, never by widening the guard.
21. **The reported window status is stage 2's tiebreak-proof, not stage 1's
    cost-proof** (4B.7, observed, NOT changed). `_two_stage_solve` returns
    `status=s2.status`, so the regenerated fixture reads **FEASIBLE** over a
    ledger the A0/A0s arms prove **OPTIMAL** on 5/5 seeds. Stage 2 exhausting its
    2.0 budget without proving the START SUM optimal says nothing about whether
    the COST was proven, and the document has no field that distinguishes them.
    Pre-existing (rolling reported stage 2's status before this session too), but
    newly conspicuous now that the ledger sits at a provable optimum. It is also
    a decision entangled with §5a.19: fixing the budget allocation may make the
    question moot. *Fix shape:* carry both statuses, or report stage 1's and name
    the tiebreak's separately — either way a contract-surface decision.
    **DISCHARGED 2026-07-28 (Session 4B.8 CU3), by RULING rather than by fix** —
    which of the two statuses "the solve status" meant had never been decided, so
    there was nothing to call a bug. Both halves of the fix shape were taken: the
    EXISTING field carries STAGE 1's status (the COST proof, which is what a
    planner asking "is this optimal?" means) and NEW optional fields
    `tiebreak_status` / `tiebreak_skipped_reason` carry stage 2's. Contract
    **1.9 -> 1.10**, additive in shape — with the honest caveat that the MEANING
    of the existing field changes on any two-stage run, recorded in the contract
    history. A schedule whose cost is proven optimal now says so, and an unproven
    tiebreak never downgrades that claim. Fixing §5a.19 did NOT make the question
    moot: at 120 orders and above stage 2 still exhausts whatever it is given.
    Ruling verbatim in docs/04 2026-07-28. See §5a.23 for what still cannot say
    it.
22. **The r5 exam bank's card expectations are invalidated AGAIN** — **DISCHARGED
    2026-07-30 (Session 4B.17).** The bank is recalibrated against the pinned
    world's persisted document, extended 27 → 33 questions, and GRADED over six
    runs; the card constants are re-derived from the committed fixture
    (+$32.20 = reopt $0.00 + move +$32.20). The ordering this entry demanded was
    honoured — re-derive from the world FIRST, then grade — and the derivation
    needed no fresh world, because the exam target was verified byte-identical to
    the registry's `rolling-c362baa4-1b0` apart from ids. **What the discharge
    also found: the specimen this entry was protecting has degenerated.** 4B.7's
    own change made `reopt_delta_abs` 0.00 BY CONSTRUCTION (§5a.12), so move
    equals total and "what did the move itself cost, not the re-solve" can no
    longer discriminate; it is reported as unexercisable rather than counted as a
    pass. See §5a.54 and `docs/closeouts/4B.17.md`. *Original entry:* (4B.7,
    NAMED not fixed, per the session's own out-of-scope list).
    `ai_exam/runner.py:317-320,377` hard-codes `_SHIPPED_CARD_REOPT_DELTA =
    -11975.83` and a `tardiness` delta of the same figure; 4B.6b corrected those
    expectations to the then-shipped card, and this session moves the card again
    (reopt to **0.00**, total to **32.20**). The exam WORLD also changes —
    `build_rolling_exam_run.py` solves the same plant under the new objective.
    **Nothing was recalibrated**, because the bank has still never been graded:
    `regression_founder_r5` remains UNRUN after four sessions for want of an
    `ANTHROPIC_API_KEY` (§5a.7), and calibrating expectations against a bank
    nobody has run would be fitting to a number of unknown quality. Whoever
    obtains a key must re-derive these figures from a fresh exam world FIRST.
    **UPDATE 2026-07-28 (Session 4B.8):** the KEY BLOCKER IS GONE (§5a.7 — it was
    loader wiring, never a missing key), but the bank was still NOT run and NOT
    recalibrated, per this session's out-of-scope list. The invalidation ALSO
    deepens: 4B.8 changes the reported window STATUS (contract 1.10, §5a.21) and
    the budget split (§5a.19), so a fresh exam world differs from the r5 world in
    more than the card figures. The ordering above still stands, and is now
    actionable: re-derive from a fresh world FIRST, then grade.
23. **"Provably optimal" is a claim the system can now make and NOTHING VOICES** — **DISCHARGED 2026-07-28 (Session 4B.11 CU1).** `src/mre/modules/cost_proof.py` is the single definition of the claim; the cockpit's top strip renders it as a chip beside the certificate grade (label and title composed SERVER-SIDE and delivered on `/meta`, so the JS composes no wording and the two surfaces cannot disagree), and the answer surface carries an unprompted rider appended by the ONE delivery seam both renderers share. The rider's rule is narrow on purpose: it fires **only when the board is UNPROVED *and* the delivered text states money** — a proved board adds nothing (the strip already says so) and "ORD-14 is on M-02" is not a cost claim. Every bundle leaving `Explainer.route` carries the proof, stamped at the one dispatch rather than in forty assemblers. It is read from the M6 `solve_complete` event — the same record the document's `SolverBlock` is built from — so the board and the answer agree because they read ONE record. **The rolling path could not state a gap at all** before this: `assemble_rolling_document` wrote `SolverBlock(gap=None)` unconditionally, so an unproved rolling board could say "not proved" and never "by how much"; `RollingView` now carries stage 1's `objective` and `gap`. `tiebreak_skipped_reason` is voiced, so a tiebreak that never ran is distinguishable from one that ran and won nothing. **What is NOT built and is now §5a.29: a "is this schedule optimal?" ROUTE** — a new intent is a vocabulary-class change, and the brief's own instruction was to name that debt rather than bolt one on. *Original entry:*
    (4B.8 CU3, NAMED not built — the brief's own instruction was to name the debt
    rather than bolt on a route). Contract 1.10 carries two distinct proofs —
    `solver.status` (COST) and `solver.tiebreak_status` (TIEBREAK) — and no
    surface renders either. **The cockpit never references `solver.status`
    anywhere in `src/cockpit/src/`**, and the answer surface
    (`explainer.py` / `renderers.py` / `rolling_questions.py`) reads no solve
    status at all, so a planner cannot ask "is this schedule optimal?" and get
    the answer the document now holds. Before this session the omission cost
    nothing, because the single status field was reporting the WRONG proof; now
    it withholds the strongest claim the product has. This is an **R-AI1** debt
    (the answer surface's coverage of run-level facts), not an R-SC3 one — the
    solver side is complete. *Fix shape:* one route/one strip element that states
    the COST proof plainly and names the tiebreak proof separately, never fusing
    them, and never letting an unproven tiebreak downgrade a proven cost. It must
    also voice `tiebreak_skipped_reason`, or a tiebreak that never ran will read
    as one that ran and won nothing.

    **SEVERITY RAISED 2026-07-28 (Session 4B.10, §5a.27).** When this was written
    the omission looked like a withheld boast. It is not. At the real plant's
    real density the cost proof is MARGINAL: five runs of one 137-ops/machine
    instance differing only in the solver seed split 4 OPTIMAL / 1 FEASIBLE, and
    the unproved run's ledger is **13.056% more expensive** than the optimum the
    other four prove to the cent. **`solver.status` is the only thing that
    distinguishes those two boards, and nothing renders it.** A planner can be
    shown a schedule 13% off the optimum with no indication that the system
    knows it could not prove it. This is no longer a completeness gap in the
    answer surface; it is the difference between a truthful board and a
    misleading one.
24. **THE REAL BOOK — the measured shape of the pilot plant** (Session 4B.9,
    read-only pandas over `raw_data/`; made durable here by 4B.10's first act,
    because a number that lives only in a close-out does not exist). **R-SC1
    stands: this is INTELLIGENCE, never a fixture.** Reference point
    `REF = 2025-03-25` (max `CreatedDate`, normalized); due date =
    `ScheduleDate`, the retired adapter's own mapping (`raw_adapter.py:748`).

    **(a) THE DUE-DATE HISTOGRAM — this book has no long tail.** 3,472 open work
    orders, 11 facilities carrying volume.

    | bucket | count | share | cumulative |
    |---|---|---|---|
    | PAST DUE | 272 | 7.83% | 7.83% |
    | 0–7 days | 1,466 | 42.22% | 50.06% |
    | 8–14 days | 1,386 | 39.92% | 89.98% |
    | 15–30 days | 299 | 8.61% | 98.59% |
    | 31–60 days | 49 | 1.41% | 100.00% |
    | 61+ days | 0 | 0.00% | 100.00% |

    `min −1573 d · p25 2 d · MEDIAN 7 d · p75 9 d · p90 15 d · max 34 d`.
    Half of committed demand is due inside a week, 90% inside a fortnight, and
    **nothing at all beyond 60 days**. The entire order book lives inside the
    horizon the engine already calls "fine". The 7.83% past-due bucket was
    EXCLUDED by the retired adapter (`raw_adapter.py:7`), so any figure derived
    through that path silently dropped 272 orders.

    **(b) ONE FACILITY IS THE PLANNING UNIT — verified on live work, not assumed.**
    Routes spanning >1 facility prefix: 1 of 3,856; restricted to the 134 routes
    open work actually uses, **0 of 134**; open WOs whose `FacilityCode` disagrees
    with their route's workcenter facility, **0 of 3,472**.

    **(c) PER-FACILITY OPS PER WINDOW** (ops = active `RoutingLines` of the WO's
    route; past-due orders INCLUDED — they are work that must be done):

    | fac | orders | ≤7d ord | ops ≤7d | ≤14d ord | ops ≤14d | ops/order | machines* |
    |---|---|---|---|---|---|---|---|
    | F006 | 851 | 329 | 1,316 | 805 | 3,220 | 4.00 | 4 |
    | F00A | 638 | 464 | 1,906 | 616 | 2,518 | 4.09 | 6 |
    | F00Z | 504 | 212 | 957 | 471 | 1,993 | 4.23 | 12 |
    | F005 | 400 | 248 | 1,974 | 347 | 2,766 | 7.97 | 10 |
    | F008 | 354 | 86 | 258 | 279 | 837 | 3.00 | 3 |
    | F004 | 276 | 150 | 600 | 259 | 1,036 | 4.00 | 4 |
    | F001 | 261 | 122 | 1,045 | 170 | 1,488 | 8.75 | 26 |
    | F00B | 108 | 75 | 610 | 99 | 812 | 8.20 | 14 |
    | F00D | 76 | 49 | 307 | 74 | 482 | 6.51 | 8 |
    | F00Y | 3 | 2 | 24 | 3 | 36 | 12.00 | 12 |
    | F002 | 1 | 1 | 3 | 1 | 3 | 3.00 | 3 |
    | **TOTAL** | **3,472** | **1,738** | **9,000** | **3,124** | **15,191** | **4.94** | **102** |

    \* machines TOUCHED by routes open work uses — the number a planner schedules
    against. Orders per facility: `min 1 · p25 92 · MEDIAN 276 (F004) · p75 452 ·
    max 851 (F006) · mean 315.6`. **200 orders is BELOW the median facility**
    (~40th percentile); six of eleven carry more.

    **(d) THE pilot_scale GAP TABLE** — `pilot_scale` is **CALIBRATED, not
    invented** (citation chain: `tools/extract_pilot_profile.py` →
    `pilot_profile.json` + `PROFILE_PROVENANCE.md` → `_apply_pilot_scale`
    (`generate_erp_dataset.py:1078`) → docs/04:6359-6363 → §5a's R-SC1 demotion).
    The useful product is the GAP:

    | axis | BOOK (measured) | pilot_scale | verdict |
    |---|---|---|---|
    | order count | median facility 276, range 1–851 | 400 preset / 200 exam | ABOVE median; in range |
    | machine count | 9 defined / 8–12 scheduled median; 39/26 max | 15 defined, 13 loaded | ABOVE median, below max |
    | route length | **4.94 ops/order** (median 4, p90 8, max 12) | **2.48 ops/order** | **HALF the book** |
    | due-date spread | median 7 d, p25 2 d; 50.1% ≤7d; 90.0% ≤14d | median 15 d, p25 12 d; 6.1% ≤7d; 45.9% ≤14d | **DIVERGENT** (−36 pp / −44 pp) |
    | past due | 7.83% (F005: 25%) | **0% — structurally impossible** | ABSENT |
    | order quantity | p50 500, p99 200,000 | truncated to a 720-min shift | named in PREDICTIONS.md |
    | arrival rate | ~5,300 SO lines/wk | not modelled | ABSENT both sides |

    **The due-date divergence is DELIBERATE and documented in the source**
    (`generate_erp_dataset.py:1197-1200`): spread wider than the raw median "so
    the plant is moderately loaded … the regime where a longer look-ahead
    actually buys cost". Mechanism: `lead_p50 = max(14, int(p50)*2) = 14`,
    `lead_min = 4`, `lead_max = 30`, `triangular(4, 30, mode=14)`. Simulated at
    400k draws: `min 4 · p25 12 · median 15 · p90 23 · max 29`. **The 8–14 bucket
    matches almost exactly (−0.14 pp); the divergence is mass moved out of 0–7
    and into 15–30.** The ROUTE-LENGTH gap is separate and was **not** documented
    as deliberate.

    **(e) THE SIX FINDINGS THAT CHANGE SOMETHING** (4B.9 F1–F7, condensed):
    **F1** the book has no long tail — 14 days is nearly the WHOLE plant, not a
    partial view. **F2** and that is the problem: a median facility's 14-day
    window holds ~1,036 operations and 4B.8's cost objective returned UNKNOWN at
    313. **F3** `pilot_scale` is calibrated with one large deliberate divergence
    (due dates) and one undocumented one (route length). **F4** past-due work has
    never been exercised, from two independent directions — `lead_min=4` makes it
    structurally impossible in the generator, and the retired adapter filtered it
    on intake. **F5** "174 workcenters" is a CORPORATE total; a median facility
    schedules 8–12 and the largest 26 — and the "13 machines" in docs/04:11234 /
    docs/07:1583 is `n_machines`-carrying-ops from the cliff sweep, not the
    plant's machine count, which is **15**. **F6** the route master overstates by
    2× (median 8 ops/route across 3,856 routes, but only 134 short routes are
    used — 4.94 ops/order actual). **F7** this backlog turns over weekly (88.8% of
    open WOs created in the last 7 days; sales intake flat at ~5,300–5,500
    lines/week across two years).

    **WHAT THE EXTRACT CANNOT SUPPLY** — named, checked in the data, never
    estimated: calendars/shifts/holidays; machine alternates (of 30,594
    `(RoutingCode, Sequence)` pairs, **exactly ZERO** have >1 row — every routing
    step names ONE workcenter); setup families and the changeover matrix;
    priority/customer weight; per-machine cost rates; **WIP/progress**;
    splittable flags; dwell; precedence beyond a linear chain; overtime windows;
    earliness preference. PRESENT BUT EMPTY: `RoutingLines.TargetTime` is
    `00:00:00.0000000` on **100.00%** of rows (one distinct value — the sentinel
    fingerprint in its purest form), `ResourceCode` 100% null, `TrackMode` one
    value. PRESENT AT THE WRONG GRAIN: `SetUpMinutes` / `ProductionMinutes` are
    per **PRODUCT**, not per operation.
25. **LOAD, NOT OP COUNT — the duration semantics are DETERMINED, and 7% of the
    book carries placeholder durations** (Session 4B.10 item 1, read-only pandas;
    R-SC1 stands). Ops are not minutes and the solver feels minutes, so 4B.9's
    op counts were converted to WORKLOAD.

    **(a) THE SEMANTICS ARE DETERMINED, not ambiguous — three independent lines
    of evidence agree.** `ProductionMinutes` is **PER LOT** (per
    `CostingLotSize` units) and the full rate applies to **each operation
    independently**; `SetUpMinutes` is **per operation**:

    ```
    op_minutes    = SetUpMinutes + (WoQuantity / CostingLotSize) * ProductionMinutes
    order_minutes = n_active_routing_lines * op_minutes
    ```

    (1) The previous-generation production code computes exactly this, per
    routing line, inside its per-line loop — `legacy/Formatnewjobs.py:68`,
    `proc_time = int((wo_quantity / casting_lot_size) * production_minutes)`,
    with `setup_minutes` taken per line. (2) The repository already RULED it:
    `legacy_author_definition_v1`, docs/04:693-701, confirmed 2026-07-07, and
    `raw_adapter.py:621` implements it. (3) **The data itself confirms the
    per-LOT reading**: log-log correlation of `ProductionMinutes` against
    `CostingLotSize` is **r = +0.683** (n = 20,131), and the median
    `ProductionMinutes` rises monotonically with the lot band — lot 1 → PM 1;
    1k–10k → 51; 10k–50k → 874; 50k+ → 1,663. A per-ORDER or per-UNIT figure
    would be independent of the lot size. **No second reading is reported,
    because none survives.**

    **(b) A SENTINEL CLASS CARRIES 94% OF THE COMPUTED LOAD.** 1,434 of 20,743
    products (6.9%) read `CostingLotSize = ProductionMinutes = SetUpMinutes = 1`
    — **all three columns exactly 1 on 100.0% of those rows**, against a median
    `ProductionMinutes` of 549 for every other product (only 0.31% of which read
    1). This is the repeated-identical-value fingerprint the carry-forwards
    already warn about. **227 open orders (7.01%) are in the class and they carry
    93.56% of all computed machine-minutes** — the largest is `PP10293020`,
    `WoQuantity = 10,000,000` at `lot=1, PM=1` → 30,000,003 minutes (41,667
    shifts) for one order. Any utilisation figure that includes them is
    measuring a placeholder. **They are NOT excluded by the retired adapter**,
    whose exclusions fire only on `CostingLotSize == 0` (131 orders) or a missing
    product (104) — a `lot=1` row is well-formed and passes. Separately, 13
    orders (0.40%) have credible costing but a single op longer than a 14-day
    window on one machine (`WR10000141`: 1.1M units, lot 25,000, PM 1,350 → 82.6
    shifts on ONE op) — real resumable work, exactly R-C3's case, not a defect.

    **(c) UTILISATION PER FACILITY PER WINDOW**, on NORMAL work only (sentinel
    and monster tiers set aside), `available = touched_machines × window_days ×
    720`. **The 720-minute working day is AUTHORED — this extract has no
    calendars of any kind**, so every ratio below inherits that assumption.

    | fac | mach | ops/mach 14d | util 7d | util 14d |
    |---|---|---|---|---|
    | F005 | 10 | 190 | 1,434.7% | 1,348.0% |
    | F008 | 3 | 156 | 237.7% | 357.3% |
    | F001 | 26 | 51 | 172.5% | 122.2% |
    | F00Z | 12 | 157 | 139.1% | 99.4% |
    | F006 (largest) | 4 | **803** | 100.9% | **112.5%** |
    | F00D | 8 | 52 | 59.6% | 111.4% |
    | F00B | 14 | 41 | 62.0% | 59.9% |
    | F00A | 6 | 359 | 55.4% | 37.9% |
    | F004 (median) | 4 | **246** | 39.1% | **32.6%** |
    | F002 | 3 | 1 | 2.0% | 1.0% |
    | F00Y | 12 | 0 | 0.0% | 0.0% |

    F00Y is 0.0% only because **all three of its orders are monster-tier** (one
    op longer than the window); it is not an idle plant, it is a plant whose
    entire book is unmodelable at this granularity.

    **5 of 11 facilities are over 100% at both depths.** Book-wide 14-day
    utilisation on normal work is **210.4%**; the median facility by utilisation
    sits at **99.4%** — precisely at the boundary. (That median is over all
    eleven rows including F00Y's 0.0% and F002's single order, so it is a weak
    statistic; the F004/F006 contrast below is the load-bearing one.)

    **(d) THE POINT — the answer is BOTH, and which one depends on the
    facility.** At the LARGEST facility (F006: 851 orders, 4 machines, 803
    ops/machine at 14 days) a real 14-day window is **structurally
    over-capacity at 112.5%**, so the difficulty there is the PLANT and the
    honest product answer is a shorter window with tardiness priced, not a
    deeper one — an instance sitting at the feasibility boundary is the hardest
    known class. At the MEDIAN facility (F004: 276 orders, 4 machines, 246
    ops/machine, 984 ops in a 14-day window) the plant is only **32.6% loaded**
    — comfortably feasible — and 4B.8's cost objective returned UNKNOWN at 313
    free ops. **There the difficulty is OURS.** The two cases must not be
    conflated: a capacity answer cannot fix F004 and a solver answer cannot fix
    F006.

    **(e) FOUR MACHINES IS THE REAL SHAPE, CONFIRMED.** The two facilities that
    matter most both schedule **4 machines** and carry **246–803 ops per
    machine** in a 14-day window. `pilot_scale` runs 13–15 machines at ~24
    ops/machine. **Every scale number the programme holds was taken on the wrong
    axis** — which is what `facility_real` (item 2) exists to correct.
26. **PAST-DUE WORK VANISHES, AND THE PER-ORDER ROUTES CANNOT SAY SO** — **DISCHARGED 2026-07-28 (Session 4B.11) by R-PD1**, ruled verbatim in docs/04. Past-due unstarted demand is now SCHEDULED, not excluded (21 of 21 on the specimen); the M0/M3 disagreement is gone because M3 no longer removes anything for being late, and clause (3)'s general guard is committed as a test (`tests/test_pastdue_disposition.py`) so the THIRD instance of this defect class is caught in whatever module invents it. **A SECOND EXCLUSION SITE was found in the process** — Check 5's resumable window-fit test floors `elapsed_days` at 0, so every past-due resumable demand would have been excluded there as `INFEASIBLE_SUBSET` instead: the same removal wearing a different code. All three measured answers are fixed and pinned. **The undiagnosed "60 of 102 / 42 excluded" note is RECONCILED** — see the v2.55 banner for both root causes. **STILL OPEN from this item's family: §5a.1** (`--horizon-days` on the `scenario.py` path adds beyond-horizon demands to `excluded_demand_ids` with NO finding at all, so nothing names the module or the reason — now formally a clause (2) AND clause (3) violation). *Original entry:*
    (Session 4B.10 item 4 — REPORTED, deliberately NOT fixed; the ghost-job
    re-ruling is a design conversation and this session's job was to hand it a
    live specimen and a number). Until now no fixture could ask the question:
    `pilot_scale`'s `lead_min = 4` makes a past-due order structurally
    impossible and the retired RawAdapter filtered past-due rows on intake
    (`raw_adapter.py:7`) — two independent blind spots over the **272 real
    past-due orders (7.83%; F005 carries 25%)**. `facility_real_pastdue`
    produces them. Specimen world: 60 orders, 21 past due.

    **(a) IT VANISHES — 21 of 21, before the solver.** Not scheduled late, not
    partially placed: `plant.schedulable_demands` drops every one.

    **(b) THE MECHANISM — and it is TWO SITES, not one, disagreeing.** The same
    finding code is raised twice with **opposite dispositions**:

    - **M0, the conformance gate.** Rule `ids.order_dates_internally_consistent`
      raises one `TEMPORAL_IMPOSSIBILITY` / WARNING covering all 21 orders with
      `outcome: degraded` and **`disposition = proceeded_flagged`**. The
      submission grades **CONDITIONAL, `go = True`** — the gate sees the
      past-due orders, names them, and *deliberately passes them on*.
    - **M3, the validator** (`src/mre/modules/validator.py:186-221`, Check 1).
      A Demand whose `due < reference_date` **and which carries no
      `in_progress`/`complete` wip_operations** is added to
      `excluded_demand_ids` with `disposition = EXCLUDED`. Then
      `PreparedPlant.schedulable_demands` (`rolling_horizon.py:385`) subtracts
      that set and the order is gone.

    So **the gate's `proceeded_flagged` promise is not honoured downstream**: M0
    says "proceed with these, flagged", M3 removes them, and nothing reconciles
    the two. It is not gravity admission — the demand never reaches `_admit`.
    The **only** escape is the docs/06 §5.13 `wip_status` doorway, which the
    extract cannot populate because it carries no WIP field of any kind
    (§5a.24). *(A CONDITIONAL grade on `facility_real` is therefore CORRECT and
    expected — it is the past-due orders, not a defect in the preset.)*

    **(c) IT IS NOT IN THE DOCUMENT AT ALL.** The assembled contract-1.9 rolling
    document is 111,839 characters and contains **zero** occurrences of the
    specimen's order id, of `TEMPORAL_IMPOSSIBILITY`, or of the strings
    `excluded`, `past due`, `past_due` or `temporal`.
    `RollingVocabulary.resolve('ORD-000014')` returns **None** — the order is not
    a known subject. It is **not** beyond-horizon either, so 4B.5's guarantee
    that "a tray order is never *not in this schedule*" does not cover it.

    **(d) THE ASK PATH: the fact IS reachable, but only by the aggregate door,
    and it is filed under the wrong category.** Measured against the live path
    with a key present:

    | question | answer |
    |---|---|
    | *where is ORD-000014?* | "**Nothing scheduled for ORD-000014.**" — true, and indistinguishable from an order that was simply not placed |
    | *why isn't ORD-000014 scheduled yet?* | "isn't in the beyond-horizon list — it's either already in the current window (committed or active) or **not part of this schedule**" — a disjunction **neither branch of which is true**, pointing back at the route above |
    | *which orders are already late?* | "**No late orders found in this schedule**" in a world where 35% of the book is past due, plus a trailing note counting exclusions **by raw canonical UUID** |
    | *why was &lt;id&gt; excluded?* | **reaches it**: route `excluded-orders`, register `testimony`, 21 records, every order named by ORDER ID with its reason |

    **(e) THE CATEGORY ERROR, which is the finding that matters.** The working
    door answers "**21 data-quality problem(s)** … has dates that can't both be
    true … *Want the fix-first ordering?*". A released work order that is
    genuinely late is **not a data defect and has no fix** — it is the plant's
    actual position, 7.83% of this book. This is the **same shelving error
    §5a.1 already names for `--horizon-days`**: a real-world category filed as a
    data-defect category. Three further consequences, all measured: the answer
    is an AGGREGATE (asking about ONE order returns all 21, subject resolved as
    "excluded orders"); the per-order routes never reach it; and the lateness
    route actively contradicts it. **Not re-ruled here.** *Fix shape, for the
    design conversation:* a past-due unstarted demand needs a disposition of its
    own — distinct from both a data defect and a beyond-horizon tray order — and
    the per-order placement routes need to voice it, or the most operationally
    urgent work in the book stays invisible to every question a planner would
    actually ask about it.
27. **THE CLIFF IS THE ONSET OF TARDINESS, NOT DENSITY AND NOT UTILISATION**
    (Session 4B.10 item 3; `tools/spikes/density_4b10/`).

    > **SUPERSEDED IN ITS NUMBERS, 2026-07-28 (Session 4B.12, §5a.31). THE
    > FIGURE 137 IS NO LONGER THE CLIFF; the MECHANISM below is confirmed and
    > strengthened.** Everything in this item was measured on a pipeline that
    > silently EXCLUDED past-due demands. R-PD1 (4B.11) admits them, and
    > re-running these exact cells against the identical worlds moves the cost
    > proof's last all-OPTIMAL density from **137 to 92 ops/machine**. Read (d),
    > (e) and (g) — the mechanism, its caveat and its explanatory power — as
    > still current. Read every NUMBER in (a), (b), (c) and (f), including 137,
    > 13.056% and 165×, as a measurement of a plant that dropped its late work.
    > (h)'s honesty about bracketing is what 4B.12 discharged: F004 and F006 are
    > now SOLVED, not inferred. The original figures are left standing rather
    > than rewritten — they are the before half of the comparison.

    Measured on
    `facility_real` — 4 machines, 4-op routes, the book's due-date histogram —
    with all three conditions the brief required: the **cost-only** objective as
    shipped since 4B.7, the **P3 allocation** as shipped since 4B.8 (the sweep
    calls `rolling_horizon._two_stage_solve`, it does not transcribe it), and
    the **wall ceiling raised to 1800 s** so the deterministic budget is what
    binds. `wall_truncated` is FALSE on every reported row; `analyze.py`
    excludes any row where it is not and refuses a file containing a duplicated
    cell. Window 14 d, frozen 3 d, `det_total` 6.0 (stage-1 cap 5.5).

    **(a) WHERE THE CLIFF IS — and it is NOT A LINE.** At `alternates=1` (the
    extract as measured), the multi-seed pass shows a **region where the budget
    is marginal and the SEED decides**:

    | ops/machine | util | n | proved | units to proof (range) | ledger spread |
    |---|---|---|---|---|---|
    | 22 | 4.2% | 1 | 1/1 | 0.0002 | — |
    | 46 | 10.3% | 1 | 1/1 | 0.0015 | — |
    | 94 | 19.0% | 5 | **5/5** | 0.015 – 0.192 (med 0.041) | **0.000%** |
    | **137** | **27.4%** | 5 | **4/5** | **2.294 – 5.594** (med 3.049) | **13.056%** |

    Below the cliff the proof is free — three orders of magnitude of headroom at
    94, and five seeds agree on the ledger **to the cent**. At 137 the proof
    costs 2.294–5.594 units against a **5.5-unit stage-1 cap**: four seeds fit
    and one does not. Seed 42 exhausts the budget, returns FEASIBLE at an 11.47%
    gap and lands on **33,298.77** where the other four prove the optimum at
    **29,453.35**, identical to the cent — **a 13.056% penalty decided by
    nothing but the random seed.** This is the same failure mode 4B.8 CU1
    measured for the OLD budget split at 200 orders (seeds needing 4.542/4.962
    against a 4.0 cap), now reproduced on the REAL shape at the REAL density
    against the NEW cap; the 1/12 reserve neither caused it nor cures it.

    **Both real facilities are past it** — F004, the median, runs **246**
    ops/machine in a 14-day window; F006, the largest, runs **803**.

    **(b) ALTERNATES HELP THE LEDGER AND HURT THE SEARCH, at wildly different
    rates.** A controlled comparison: machine count and total load are identical
    across arms (same ops, same required minutes, same utilisation), so only
    assignment combinatorics change.

    | ops/machine | ledger a=1 | ledger a=2 | delta | proof a=1 | proof a=2 | ratio |
    |---|---|---|---|---|---|---|
    | 22 | 4,650 | 4,606 | −0.93% | 0.0002 | 0.0006 | 3× |
    | 46 | 10,229 | 10,120 | −1.07% | 0.0015 | 0.0802 | **52×** |
    | 94 | 20,379 | 20,085 | −1.44% | 0.0150 | 2.4746 | **165×** |

    Those columns are the **seed-42 pair**, so the ratio is like-for-like.
    Stated honestly: `alternates=2` was measured at ONE seed while
    `alternates=1` has five at 94 ops/machine spanning 0.015–0.192 units, so
    against that whole range the a=2 cost is **13×–165×, median 60×**. The
    direction is not in doubt at any seed; the exact multiple is a one-seed
    figure and is labelled as one. The saving grows slowly; the proof cost grows
    by one to two orders of magnitude over the same span. Cross-training is
    worth having for the schedule it produces, but on this shape it is what
    exhausts the budget first.

    **(c) UTILISATION IS REFUTED AS THE PREDICTOR — twice, and the second
    refutation is fatal to the whole idea.** The hoped-for outcome was a load
    ratio computable BEFORE solving that the gate could warn on.

    1. **Eligibility is invisible to load.** At 110 orders the two arms have
       IDENTICAL utilisation (19.02%) and IDENTICAL ops per machine (94), and
       their proof costs differ by **165×** (seed-42 pair). No function of load
       can separate two cells whose load numbers are equal.
    2. **The seed decides.** At 137 ops/machine, five runs differing ONLY in the
       solver's random seed split **4 OPTIMAL / 1 FEASIBLE** with a 13.056%
       ledger spread. **Every pre-solve quantity is identical across those five
       runs**, so no rule computable before solving can distinguish them.

    `analyze.py` prints both verdicts itself: *UTILISATION separates the two
    classes cleanly: **False***; *OPS/MACHINE separates the two classes cleanly:
    **False***.

    **So the hoped-for gate warning does not exist in this form.** The cliff is
    not a line in density to be predicted; it is a REGION where the budget is
    marginal. What can be known is not *predicted* but **REPORTED** — the solve
    knows whether it proved the cost optimum, and since 4B.8 CU3 `solver.status`
    carries exactly that. **Which makes §5a.23 considerably more serious than it
    looked when it was written:** at real density the difference between a
    proved and an unproved window is **13% of the ledger**, and no surface says
    which one the planner is looking at.

    **(d) WHAT DOES PREDICT IT — priced in two experiments, the second of which
    CORRECTED the first explanation.** Every cell with tardiness 0 proved the
    optimum; the first cell with tardiness > 0 (7,049 minutes, 8 late demands)
    failed. The counterfactual (same instance, changing ONLY the tardiness
    weight) at 137 ops/machine: **PRICED FEASIBLE, 5.59 units, gap 11.47%;
    FREE OPTIMAL, 4.72 units, gap 0.** The tempting reading — that with one
    eligible machine the rest of the objective is a CONSTANT — predicts a
    near-instant proof, and 4.72 units is not that, so it was tested rather than
    asserted. Evaluating `sum(objective_terms)` at several different feasible
    solutions of the same model (eligible-set sizes verified `{1: 548}`, so the
    assignment really is forced):

    | | spread across feasible solutions |
    |---|---|
    | tardiness PRICED | 4,973,436 … 5,888,641 = **18.402%** |
    | tardiness FREE | 2,967,852 … 2,970,665 = **0.095%** |

    **The objective is not constant — it is NEARLY FLAT.** The correct statement
    is that at `alternates=1` the placement-dependent part of the cost is
    *almost entirely tardiness*: freeing it collapses the spread by a factor of
    **194**. Below the cliff nothing is late, the objective barely moves between
    schedules and the first solution is already within a whisker of optimal;
    above it tardiness dominates, the objective spreads 18%, and the budget
    cannot close the search. (Proving a nearly-flat objective is not free
    either — the FREE arm still spent 4.72 units closing 0.095%.)

    **(e) THE CAVEAT THAT MUST TRAVEL WITH THIS.** The decomposition is a
    property of `facility_real`'s authored physics, and those choices
    *faithfully mirror the extract*, which carries no setup families, no
    changeover matrix and no overtime windows at all (§5a.24). A real plant that
    DOES price changeovers would have a placement-dependent cost term even at
    `alternates=1`, and its cliff would not sit at 137. **What generalizes is
    the shape of the rule — difficulty turns on how much of the objective
    actually varies with placement — not the number.**

    **(f) DOES THE GAP PROBE'S VERDICT SURVIVE THE OBJECTIVE CHANGE? NO, AND
    NOT IN THE DIRECTION HOPED.** The probe's "F004 solved near 260, F006 died
    near 850" was taken with the priced earliness term 4B.7 removed. Removing it
    should have made things easier. Instead, on the real shape the cost proof is
    already lost at **137** ops/machine — *below* F004's real 246 and far below
    F006's 803. **Both real facilities are past the cliff, at a 14-day window,
    on the shipped objective and the shipped budget.**

    **(g) THIS EXPLAINS 4B.8's UNRESOLVED "NOT GENERAL".** §5a.15 recorded that
    at 200 orders optimality is proved at 123 free ops while at 120 orders it
    fails at 115 — "so neither `n_free` nor ops/machine predicts it" — and left
    the cause open. **(d) is the missing predictor**: those two instances differ
    not in size but in **whether their due dates can be met**, and it is
    tardiness, not op count, that makes the objective vary enough to be hard.
    The 8-to-9-day cliff 4B.8 found at 200 orders is the depth at which that
    plant first goes late. §5a.15 is **NOT discharged** — it was measured on
    `pilot_scale`, whose due-date spread is deliberately widened, so the depth
    itself does not transfer — but its "not general" puzzle now has a mechanism.

    **(h) COVERAGE — what was and was NOT measured.** MEASURED: 22 / 46 / 94 /
    137 ops per machine (orders 28 / 55 / 110 / 165); **both** alternate
    settings at 22 / 46 / 94; `alternates=1` at 137; seeds 42–46 at the two
    bracket densities (94 and 137) for `alternates=1`. NOT MEASURED: anything
    above 137 ops/machine, `alternates=2` at 137 and above, and seeds 43–46 at
    the two lightest densities. The reason is cost, stated rather than hidden:
    every cell above the cliff spends the full budget and the `alternates=2`
    cells there run to tens of minutes each, so the session spent its time
    LOCATING the cliff and PRICING its mechanism rather than characterizing how
    bad it gets past it. **Consequence for the headline claim:** F004's 246 and
    F006's 803 ops/machine are **BRACKETED, not directly solved** — "both real
    facilities are past the cliff" follows from the cliff sitting at 137 *plus*
    the assumption that difficulty does not *decrease* with density above it.
    That assumption is consistent with the 22→137 series and with 4B.8's
    higher-density results, but **it is an inference, not a measurement**, and
    those two densities are the obvious next cells to run.


28. **R-PD1 CLAUSE (5) IS OPEN — AGE IS NOT LATENESS, AND THE PLANT IS TOLD
    NOTHING ABOUT THE AGE OF ITS BACKLOG** (Session 4B.11, NOT built, and the
    reason it was not built is the finding). Clause (5) rules that a demand past
    due beyond a **declared** threshold raises a data-quality finding about its
    AGE — informational, and the demand is still scheduled. The distinction is
    real and the data shows why: the book's minimum due date is **−1573 days**
    (§5a.24). Three days overdue is the plant's normal position; four years
    overdue is very likely a record nobody closed, and *that* is a data-quality
    question with a real fix.

    **Nothing is emitted, because the threshold is a business judgment only a
    human may state.** There is no defensible default — "past due beyond N days
    is suspicious" depends entirely on the plant's own close-out discipline — and
    choosing an N here would author a business fact we do not have. This is the
    same discipline `earliness_value` (R-SC3(3)) and the coarse zone's
    `capacity_derate` already follow: **an undeclared plant is never given an
    invented margin.** Emitting an age finding with no declared pathway would be
    evidence with nothing behind it, which is worse than silence.

    Recorded in **docs/06 §5.9** with the full §8 pipeline-proof chain it would
    require, none of it done: the `refinements.past_due_age_threshold_days`
    doorway; a gate check on the *declared* value only (which would move the
    registry to 37 rules — a reviewed change); adapter translation with
    provenance printed beside the value; **a NEW finding code** (`PAST_DUE_AT_INTAKE`
    must not be stretched to also mean "suspiciously old", for exactly the reason
    that code exists at all); an authored remediation note — and unlike
    `PAST_DUE_AT_INTAKE`, which carries `remediation_applies: false` because a
    genuinely late order has no fix, an AGE finding DOES have one (close or
    re-date the stale record at source); and a truth manifest plus an anomaly
    generator so the coefficient is pipeline-proven rather than model-proven.

    **The honest position until all six exist:** the plant is told nothing about
    the age of its backlog, and that silence is deliberate.

29. **THERE IS STILL NO "IS THIS SCHEDULE OPTIMAL?" ROUTE** — **DISCHARGED
    2026-07-29 (Session 4B.13 Item 2).** `solve-optimality` is in the closed
    vocabulary and answers from `cost_proof.from_evidence` — the same M6
    `solve_complete` record the document's `SolverBlock` and the strip chip are
    built from, so the answer and the board agree because they read ONE record.
    The fix shape below was followed as written: the COST proof stated plainly,
    the TIEBREAK beside it and never over it, `tiebreak_skipped_reason` voiced.
    Paid as the vocabulary-class change this entry insisted it was — `Intent`,
    `INTENT_MEANINGS`, `ROUTE_TAXONOMY`, `ROUTE_OFFERS`, the assembler, the
    authored copy and **parse prompt v10**, in one commit.

    Two things the fix shape did not anticipate. **An unproved board must not be
    slandered by its own gap**: 4B.12 measured F006 at 98.8% over a ledger whose
    spread across seeds was 0.289%, so the copy says in as many words that the
    gap is the limit of the PROOF and not a measure of the schedule's quality.
    And **`CostProof.no_solve` fuses two facts** — "nothing was admitted" and
    `status=None` (an index with no solve event, including one that could not be
    read). The route separates them, because answering "there was no solve"
    about a solve that happened is the same defect class as the rest of that
    session. Separated in the route rather than in `CostProof`, whose chip and
    rider callers want the existing three-way split.

    *Original entry (Session 4B.11 CU1, NAMED not built — the successor debt to
    §5a.23, which is discharged):* The
    cost proof is now RENDERED (the strip chip) and VOICED where it bears on a
    money claim (the unprompted rider), so a planner looking at an unproved board
    can see it and cannot be given a cost figure without its gap. What they still
    cannot do is **ASK**. "Is this optimal?" / "how close to optimal is this?" /
    "why couldn't you prove it?" reach no route: the intent is not in the closed
    vocabulary (`contracts/parse.py`), so the parse cannot name it and the
    question falls to the synthesis tier, which will answer it from the tool
    surface with no access to `solver.status` at all.

    This is an **R-AI1** debt (the answer surface's coverage of run-level facts),
    deliberately not discharged here: **a new intent is a vocabulary-class
    change** — Intent + meaning + taxonomy + offer + assembler + authored copy +
    a parse-prompt version bump, reviewed and committed with its doc update — and
    the brief's own instruction was to name it rather than bolt a route on at the
    end of a session that had already changed a contract.

    *Fix shape:* one intent (`solve-proof` or similar) dispatching to a route
    that reads `cost_proof.from_evidence` and states the COST proof plainly, the
    TIEBREAK proof separately, and `tiebreak_skipped_reason` when the tiebreak
    never ran — never fusing them, and never letting an unproven tiebreak
    downgrade a proven cost. The language already exists in `cost_proof.chip()`
    and `cost_proof.rider()`; what is missing is the door.

30. **`facility_real`'s CONDITIONAL GRADE IS A GENERATOR TRUTHFULNESS DEFECT, NOT
    THE PAST-DUE ORDERS — correcting 4B.10** (Session 4B.11, REPORTED not fixed).
    4B.10's close-out recorded that "a CONDITIONAL gate grade is CORRECT for it
    (the past-due orders), not a defect". **That is wrong**, and inspection of the
    rule shows why: M0's `ids.order_dates_internally_consistent` checks
    `due < release/created`, **NOT** `due < reference_date`. Past-dueness alone
    does not trip it and never did.

    `tools/generate_erp_dataset.py` `_apply_facility_real` writes
    `created_date = ref.isoformat()` for **every** order, so a past-due order is
    emitted as *created on the reference date and due before it* — a genuine date
    inversion, and the gate is right to flag it. A real backlog order was created
    *before* it was due. **This is the same defect docs/04's 2026-07-10 amendment
    already fixed once**, for the `stale_due_dates` anomaly: "a stale-backlog
    order was *created* long ago too, so the anomaly now ages created_date with
    the due date — the row stays internally coherent and the stale flag is a pure
    backlog signal, not a spurious inconsistency." The lesson did not transfer to
    the preset written eighteen months of sessions later.

    *Fix shape:* for a past-due order, age `created_date` with the due date (the
    book's measured median lead of 7 days is the natural authored value), and
    record it in `datasets/facility_real/PROFILE_PROVENANCE.md`'s
    measured-vs-authored table. Consequence: `facility_real` would grade
    **ACCEPTED**, matching `pilot_scale`.

    **NOT DONE IN 4B.11, deliberately, and the reason is worth keeping:** that
    inversion is what makes the specimen's M0 `proceeded_flagged` finding exist,
    and clause (3)'s general guard needs a live one to be **non-vacuous**
    (`test_the_guard_has_something_to_guard` asserts exactly that). Fixing the
    generator and the guard's specimen in the same session would have left the
    guard passing for the wrong reason. Whoever fixes this must give the guard a
    different non-vacuous specimen in the same commit.

31. **THE CLIFF IS AT 92 OPS/MACHINE, NOT 137 — AND BOTH REAL FACILITIES ARE
    NOW SOLVED RATHER THAN BRACKETED** (Session 4B.12 CU1/CU2;
    `tools/spikes/density_4b12/`). §5a.27 carries a dated supersession note
    pointing here.

    **THE MEASUREMENT IS CONTROLLED, and that is checked rather than claimed.**
    The worlds are the ones 4B.10 solved — `verify_world_identity.py` compares
    each regenerated submission to `_4b10_scratch` byte for byte (two clock
    fields masked) and all eight are IDENTICAL; `tools/generate_erp_dataset.py`
    has not been touched since 4B.10's own commit. Same generation seed (1),
    same window (14 d), same frozen front (3 d), same `det_total` (6.0), same
    1800 s wall ceiling, same shipped two-stage call. **Only the pipeline
    changed.**

    **(a) WHAT R-PD1 DID BEFORE ANY SOLVING.** Every past-due demand now
    survives to `schedulable` AND is admitted — `n_past_due_admitted ==
    n_past_due_all` at every cell measured, from 4 of 4 at 28 orders to 66 of 66
    at 851. The same order count therefore carries **more operations**: 110
    orders went from 376 free ops to 400, so 4B.10's "94 ops/machine" cell is
    **100 ops/machine** today. The density axis itself moved by ~6%.

    **(b) THE COST PROOF, SAME CELLS, SIDE BY SIDE** (`alternates=1`, seeds
    42–46, deterministic units to proof):

    | ops/machine | 4B.10 proved | NOW proved | proof 4B.10 | proof NOW | gap NOW |
    |---|---|---|---|---|---|
    | 26 (was 22) | 1/1 | **5/5** | 0.0002 | 0.035–0.069 | — |
    | 50 (was 46) | 1/1 | **5/5** | 0.0015 | 0.294–0.735 | — |
    | 100 (was 94) | **5/5** | **1/5** | 0.015–0.192 | 5.459 | 3.9–16.0% |
    | 149 (was 137) | 4/5 | **0/5** | 2.294–5.393 | — | 40.5–49.3% |

    Below the cliff the proof still lands, but it costs **200–360× what it cost
    on the same world without its late work**. 4B.10's headline cell — five
    seeds agreeing to the cent at 94 ops/machine — now splits 1/5 with an
    8.463% ledger spread.

    **(c) THE CLIFF, PINNED.** Four densities were added to locate it:

    | ops/machine | orders | util | proved | units to proof | ledger spread |
    |---|---|---|---|---|---|
    | 65 | 70 | 10.0% | 5/5 | 0.045–0.286 | 0.000% |
    | 76 | 85 | 11.1% | 5/5 | 0.576–1.024 | 0.000% |
    | **92** | 100 | 16.4% | **5/5** | 2.141–2.735 | 0.000% |
    | **94** | 105 | 24.7% | **0/5** | — (gap 2.8–33.4%) | **22.906%** |

    **The last all-proved density is 92 and the first all-failed is 94** — a
    sharper transition than 4B.10 saw, and 45 ops/machine lower. At 94 the
    ledger spread across five seeds is **22.906%**, against the 13.056% that
    made §5a.23 urgent.

    **(d) OPS/MACHINE IS REFUTED AS A PREDICTOR BY A SHARPER ARGUMENT THAN
    UTILISATION WAS: the proof cost is not even MONOTONE in density.** 65
    ops/machine proves in 0.045–0.286 units; the LIGHTER 50 ops/machine takes
    0.294–0.735. The 70-order world carries a smaller past-due burden (floor
    4,200 vs 16,800) and its solutions carry less tardiness. **Stated
    honestly:** each cell is an independent draw at its own order count, so
    between-cell differences include world variation and not density alone —
    which is precisely the point. Density does not determine difficulty, so no
    threshold in density can be a rule. §5a.27(c)'s conclusion stands, by a
    second and independent route.

    **(e) F004 AND F006, MEASURED.** §5a.27(h) recorded that both were
    BRACKETED, not solved, and named them as the obvious next cells. They are
    now run, on the calibrated profiles (276 and 851 orders — F004 and F006 as
    `PROFILE_PROVENANCE.md` defines them), `alternates=1`, seeds 42–46 (F006's
    remaining seeds were still landing at session close; its row states n=2):

    | | ops/machine | util | proved | gap | ledger spread | tardiness as % of ledger |
    |---|---|---|---|---|---|---|
    | **F004** (median) | 254 | 54.2% | 0/5 | **83.5–85.8%** | 11.121% | 90.4% |
    | **F006** (largest) | 772 | 134.9% | 0/2 | **98.8%** | 0.289% | **99.05%** |

    The inference §5a.27 flagged is confirmed: both are far past the cliff. What
    the inference could not have told anyone is the **magnitude** — an 85% gap
    at the MEDIAN facility.

    **(f) THE ANSWERABILITY RESULT, WHICH IS THE ONE THAT MATTERS FOR THE
    PRODUCT.** **Not one cell at any density returned UNKNOWN.** Every failing
    cell returned a FEASIBLE schedule that places every admitted operation, with
    a gap the solver stated itself. The satisfiability probe explains why: a
    first solution costs **0.0002–0.147** deterministic units across the whole
    ladder, against a 5.5-unit stage-1 cap that cannot close the bound — a
    factor of **37× at F006 and 948× at 149 ops/machine**, the same shape 4B.8
    measured at 74×. **The engine's problem at real density is not producing an
    answer; it is proving one.** That is what makes 4B.11's rendered gap the
    right response and a pre-solve warning the wrong one.

    **(g) F006 IS AN OVER-CAPACITY QUESTION, NOT A PROOF FAILURE — and the
    tardiness split is what makes its answer legible.** At 134.9% utilisation
    the window cannot hold the work, so the optimum itself carries enormous
    tardiness and "prove the optimum" is not the operative question. Its ledger
    is **16,887,473**, of which production is 37,472 and setup 123,520 — **0.95%
    of the total.** The other 99.05% is tardiness, and contract 1.11 splits it:
    **1,447,800 floor** (already late at intake, unrecoverable by any schedule)
    and **15,278,680 controllable**. 705 of 772 admitted demands are late.

    **A LIMIT OF THE SPLIT, FOUND HERE AND NOT FIXED.** "Controllable" means
    *not already accrued at t0* — it does NOT mean *discretionary*. On a plant
    committed to 134.9% of its window, most of that 15.3M cannot be scheduled
    away by any placement; it is a capacity fact wearing a placement label. The
    split has two categories and this plant needs three (floor / capacity-
    infeasible / genuinely placement-dependent). Naming it is the deliverable
    here; the third category needs a ruling, because computing it means solving
    a relaxation and asserting a lower bound as a business fact.

    **(h) ALTERNATES: THE REAL CLIFF IS LOWER STILL IF THE PLANT CROSS-TRAINS.**
    Daryn has confirmed the plant cross-trains, so the extract's
    single-workcenter routings are believed to be an extract limitation and
    `alternates=2` is the more realistic setting. Measured at a=2: 26 and 50
    ops/machine still prove 5/5 (at 3–5× the a=1 cost); **100 ops/machine proves
    0/5 where a=1 still manages 1/5**; 149 gives 54.6–61.0% gaps against a=1's
    40.5–49.3%; F004 gives **95.9%** against 83.5–85.8%. **So every a=1 figure
    in this item is the OPTIMISTIC one.** The a=2 cliff is bracketed between 50
    and 100 ops/machine and was not pinned — the cells cost 25–30 minutes each
    and the session spent its budget on the two real densities instead.

    **(i) COVERAGE — what was and was NOT measured.** MEASURED: `alternates=1`
    at 26 / 50 / 65 / 76 / 92 / 94 / 100 / 149 / 254 ops/machine, seeds 42–46 at
    every one; 772 ops/machine (F006) at seeds 42–46 as they land, one row
    reported here (n=2, gap identical to three decimals on both); `alternates=2`
    at 26 / 50 / 65 / 100 / 149 / 254. NOT
    MEASURED, and each for a stated reason: **the a=2 cliff pin** (cost, above);
    **F006 at `alternates=2`** — F004's a=2 cells already exceed the 1800 s wall
    ceiling on a plant a third the size, so the cell cannot produce a *reportable*
    row under this session's own configuration rule, and running it would only
    manufacture an excluded one. **THREE F004 `alternates=2` ROWS WERE EXCLUDED
    FOR WALL TRUNCATION** — in the end FOUR of the five (seeds 42/43/44/46, at
    1984–2787 s), quarantined in `cu2_f004_a2_WALLTRUNCATED.bak` rather than
    deleted. **One clean `alternates=2` row survives at F004** (seed 45), which
    is why that column reads n=1 — and it is the direct evidence that F006 at
    `alternates=2` cannot produce a reportable row, F006 being three times the
    size.

32. **THE WARM START IS A RE-ROLL, NOT AN IMPROVEMENT — IT PAYS IN THE CLIFF
    REGION AND COSTS BEYOND IT** (Session 4B.12 CU3; `hint_mode` in
    `src/mre/modules/rolling_horizon.py`, guards in
    `tests/test_hint_warm_start.py`, arms in `cu3_*.jsonl`).
    **SHIPPED BEHIND A FLAG, DEFAULT OFF, and turning it on is a ruling** — the
    numbers below do not support one.

    **THE EXPERIMENT.** 4B.8 measured that the objective is what makes the model
    hard to find anything in, not merely hard to optimize (satisfiability 0.082
    units against a cost solve that returned nothing in 6.0). §5a.31 re-measured
    that at 37×–948× across nine densities. So phase 0 clears the objective,
    solves for any feasible solution, and seeds it: **H1** hints start, end AND
    assignment vars (via the same `_hint_from_solve` the shipped stage-1 →
    stage-2 warm start already uses); **H2** hints ASSIGNMENT LITERALS ONLY —
    structure, not times, a partial hint that survives what exact times may not.
    **H0** is the shipped path. `alternates=1`, seeds 42–46.

    **PHASE 0'S COST COMES OUT OF THE SAME `det_total`** and is counted into the
    returned `det_consumed`, so the arms compare on TOTAL consumption. It is
    nearly free: **0.0024 units at 100 ops/machine, 0.0058 at 149, 0.0140 at
    254** — 0.04%–0.23% of the 6.0 budget. Cost is not why it fails.

    **THE RESULT, PAIRED SEED BY SEED AGAINST ITS OWN CONTROL** (never pooled:
    the cliff is a region where the SEED decides, so a mean over seeds hides the
    only effect there is). A WIN needs the gap better by ≥1 percentage point, so
    solver noise cannot manufacture one:

    | ops/machine | arm | n | H0 proved | arm proved | W/L/T | median gap H0 → arm | median ledger |
    |---|---|---|---|---|---|---|---|
    | 100 | H1 full | 5 | 1/5 | **2/5** | **3/1/1** | 10.1% → **2.2%** | −0.79% |
    | 100 | H2 assign | 5 | 1/5 | **3/5** | **3/1/1** | 10.1% → **0.0%** | **−4.56%** |
    | 149 | H1 full | 5 | 0/5 | 0/5 | 2/3/0 | 44.8% → 43.3% | +1.01% |
    | 149 | H2 assign | 5 | 0/5 | 0/5 | 0/4/1 | 44.8% → 46.3% | +1.05% |
    | 254 (F004) | H1 full | 3 | 0/5 | 0/3 | 0/1/2 | 83.7% → 86.4% | +3.56% |
    | 254 (F004) | H2 assign | 3 | 0/5 | 0/3 | 0/1/2 | 83.7% → 85.6% | +1.74% |

    **THE VERDICT IS OUTCOME 2 IN THE CLIFF REGION AND OUTCOME 3 BEYOND IT.**
    At 100 ops/machine — just past the cliff, where the budget is marginal — the
    hint is worth having: seed 42 goes from FEASIBLE at a 16.0% gap and a
    53,585 ledger to **OPTIMAL at 49,404, the same optimum another seed proves**,
    and the assign arm triples the proof count. At 149 it is a wash or slightly
    negative. At F004's 254 it is a liability: one of the three seeds measured
    returned a ledger of **1,080,587 against the control's 571,543** — 89%
    worse.

    **AND EVEN WHERE IT WINS IT IS A RE-ROLL, NOT AN IMPROVEMENT.** The same
    density that produces the 16%→proved win also produces a loss: seed 45 goes
    from a 3.9% gap to 8.5% (H1) and 23.0% (H2). A hint changes where the search
    starts, which in a region where the seed decides is **another way of
    changing the seed**. That is why the win column and the loss column are both
    non-empty at every density, and why no ruling follows from these numbers.

    **OUTCOME 1 COULD NOT OCCUR, and that is itself the finding.** The hint's
    largest theoretical prize was UNKNOWN → FEASIBLE. **There is no UNKNOWN to
    convert:** §5a.31(f) found that the shipped path already returns a solution
    at every density measured, up to 772 ops/machine at 134.9% utilisation. The
    74× that motivated this experiment is real, but it describes the distance to
    a PROOF, not to an answer.

    **WHAT THIS SAYS ABOUT THE DETERMINISM RULE, recorded as 4B.12's brief
    required.** CP-SAT's large-neighbourhood-search improvement workers live in
    the parallel portfolio this repository disables by hard rule (any identical
    schedule claim requires `--solver-workers 1`). A single-worker search cannot
    exploit a good incumbent the way the portfolio would. So the honest reading
    of outcome 3 is **not** "hints do not work" but "hints do not work *for us*
    at one worker", and it strengthens the case for **per-facility partitioning**
    (the 4B.10 partition ruling's corollary): partitioning buys parallelism
    without giving up reproducibility, which is the thing a hint cannot do.

    **NOT MEASURED:** `alternates=2` arms (a=1 is already the optimistic setting
    per §5a.31(h), and the a=2 cells cost 25–30 minutes each); seeds beyond the
    counts in the table at 149 and 254, where the runs were still landing at
    session close. The table states its own n per row.


33. **FOUR SLOW TEST FIXTURES HAVE BEEN RAISING `TypeError` SINCE 4B.8**
    (Session 4B.13, REPORTED not fixed). `tests/test_coarse_horizon.py` (three
    call sites) and `tests/test_coarse_binding.py` (one) call
    `build_rolling_view(..., det_time=...)` — a parameter 4B.8 CU2 renamed
    `det_total`. Every one of them is `@pytest.mark.slow`, so they are skipped
    in every normal run and **have not executed since that rename**.

    This is the same defect class the errand's AST guard
    (`tests/test_build_rolling_exam_run.py`) was built to catch, in a surface
    that guard does not read: it binds the BUILDER TOOL's call sites against
    live signatures, not the test suite's.

    **Why it was not fixed here.** The rename was not an identity. `det_time`
    was a PER-STAGE budget; `det_total` is a two-stage total from which stage 1
    is capped at total minus a 1/12 reserve. docs/04's own 4B.8 entry records
    that **no single multiplier preserves the historical budget**, which is
    precisely why every caller had to state its own — the exam/fixture builders
    went 2.0 → 4.0 and the golden driver 0.5 → 2.5. Choosing numbers for these
    four would author budgets nobody measured, and `test_coarse_horizon.py`
    carries a **digest golden** that a changed budget can move.

    *Fix shape:* state the budget chosen and why, in the same commit that
    re-derives the digest golden against it. Cheapest defensible reading is that
    each fixture wants its stage-1 budget preserved, i.e. `det_total ≈
    det_time × 12/11`, but that is a proposal, not a measurement. **Verify the
    four tests actually PASS afterwards** — they have never run, so a signature
    fix may only reveal the next failure. Consider also extending the AST
    signature guard to `tests/`, which would have caught this in 0.3 s.

34. **THE EXPLAINER'S ROW MODEL WAS CHUNK-BLIND, AND IT IS WHY THE CITED
    TIMESTAMP WAS FOUR DAYS OFF** (Session 4B.14 Item 0, FIXED).
    `Explainer._load_enriched_assignments` read `phase_windows["run"][0]["end"]`
    — the FIRST chunk of a chunked operation — so ORD-000011's end was reported
    as its first PAUSE (2026-01-08 19:00) rather than its completion
    (2026-01-12 15:37). That is exactly the figure the live answer cited.

    4B.13 fixed this class twice already, in `assemble_rolling_document` and on
    the board; the explainer's own read was never looked at, and it feeds the
    blocked-by cause, order completion, slack and the gap resolver. `end` is now
    the LAST run window's end, and the row carries `chunks`, `run_min` and
    `span_min` so a consumer can distinguish run time from elapsed span rather
    than conflating them.

    **The general lesson, and it is the reusable one:** a defect class fixed at
    one seam is not fixed. 4B.13 found the merge in the document assembler and
    the board and stopped; the same first-chunk-only read sat in a third
    consumer, producing a wrong number in prose instead of a wrong shape on
    screen — where nothing draws it, so nothing looks wrong.

35. **THE EXPLAINER KNEW ONE CAUSAL STORY AND THE PLANT HAS AT LEAST SIX**
    (Session 4B.14 Item 2, FIXED — `why-here`, parse prompt **v11**).
    `start-reason` answered every "why is it placed here" question with resource
    contention: the last job on the machine. When the true cause was one of the
    other five it reached for the only one it had and rendered it fluently, with
    citations.

    **The measured specimen.** ORD-000013's op20 waits for Thursday because it
    needs **7h11m in one piece** and PAINT-01 had **4h54m** left when op10
    finished — a docs/05 **C3** chunk-fit cause, explained as contention, citing
    a timestamp four days off. Its op10 is the same shape one step earlier:
    CUT-01 came free Monday 15:37 with 3h23m of shift left against 7h06m of
    work, so it waited for Tuesday morning.

    `blocker_analysis.py` computes an earliest-feasible-start per docs/05 family
    — release (A4), precedence (A1/A2), frozen (R-F1), pin (A7/F1), resource
    (B1), calendar (C1/C2), chunk-fit (C3) — and names the family that binds.
    The ladder is monotone by construction; BINDING is the earliest family
    attaining the maximum (the tie rule matters: when precedence and chunk-fit
    land together, precedence pushed it and chunk-fit merely failed to push
    further); RUNNER-UP is the previous pusher.

    **THE DISTINCTION THAT MATTERS MOST, and the product could not draw it:**
    `actual_start == max(est)` means IT COULD NOT START EARLIER; `actual_start >
    max(est)` means NOTHING PREVENTED IT and the solver CHOSE this placement.
    Those are different facts to a planner and the explainer asserted the first
    for both. Measured on the pinned board, ORD-000011 is a genuine `chose`:
    holding every other placement where it is, CUT-01 had open unheld time from
    Jan 6 16:15 and the solve took Jan 8 14:36.

    **Four docs/05 families are NAMED as uncomputed, on every answer**, rather
    than silently omitted: B3/B5 (secondary and cumulative resources — the
    document carries primary-lane occupancy only), B7/B8 (sequence-dependent
    changeover — a METHOD gap, not a data gap: the matrix is readable, but the
    setup an operation would need at an earlier position depends on what would
    then precede it, which is a re-solve), C4 (no adapter populates the doorway),
    F3 (unimplemented). A3 and A6 are out of scope rather than missing — they
    are UPPER bounds and can never be why something could not start earlier.

36. **CAUSAL SUFFICIENCY: A CITED CAUSE MUST ACCOUNT FOR THE QUANTITY IT
    EXPLAINS** (Session 4B.14 Item 1, FIXED — `causal_sufficiency.py`).
    "Held until T, so it took the next opening" asserts an arithmetic identity —
    the explained start EQUALS the first open window on that resource after T —
    and nobody checked it. On the specimen the next opening was Jan 9 07:00
    against a start of Jan 13 07:00.

    **The vacuity tripwire (4B.5 CU3) cannot catch this and neither subsumes the
    other.** That check asks whether an answer names anything concrete; this one
    named an order, a machine AND a timestamp, and would have passed just as
    cleanly with the timestamp off by a year. Vacuity asks whether the answer
    says anything; sufficiency asks whether what it says adds up, and needs no
    model judgment at all — it is subtraction against the persisted document.

    **A finding worth keeping: the two 4B.14 fixes are independent.** Repair the
    chunk-blind read alone and the sentence is STILL false — CUT-01 frees
    mid-shift Monday and the operation starts Tuesday morning, because the real
    cause is chunk-fit. The chunk fix makes the cited NUMBER true; only the
    blocker analysis makes the CAUSE right; only this check can tell that a
    corrected sentence is still over-claiming. Pinned in
    `tests/test_causal_sufficiency.py`.

37. **DISAGREEMENT LAUNDERING — A CHALLENGE TO THE REASONING WAS ANSWERED AS A
    QUESTION ABOUT LATENESS** (Session 4B.14 Item 3, FIXED — `ContestedClaim`).
    Measured live: "it seems it should be able to start on tuesday after op10
    finishes" — a challenge carrying the correct hypothesis — came back as "is
    ORD-000013 really on time? Yes - the record agrees."

    The intent was never wrong: it IS a contest. The ASSEMBLER knew exactly one
    proposition, and its canonical question said so — literally "is {order}
    really on time?". An affirmative that reads as agreement while addressing
    nothing that was said. **For a product whose pitch is "interrogate the
    schedule" this is the worst available failure — worse than a wrong number,
    because the planner cannot tell they were ignored.**

    The parse now REPORTS which claim is disputed (`lateness` / `timing` /
    `other`) and the dispatch answers a `timing` contest with the blocker
    analysis, on the planner's own terms; `other` says the challenge could not be
    evaluated rather than substituting an adjacent question it can answer.
    R-AI5(8)'s discipline throughout: the parse reports, the dispatch decides.

    **`predicate_coverage`'s vocabulary went from one entry to three**, both
    additions measured, never speculative: `disagreement` (this specimen) and
    `temporal_alternative` ("why can't this order start on Monday" answered with
    when it DOES start). The tripwire that forces a reviewer to look
    (`test_the_vocabulary_is_deliberately_minimal_and_stays_declared`) went red
    for both before they were reviewed in, which is what it is for.

38. **THE "WHY IS THIS HERE?" BUTTON WAS ASKING A DIFFERENT QUESTION**
    (Session 4B.14, FIXED). The cockpit's deictic button has been labelled *Why
    is this here?* since 4A.2 and fired `why is X on Y?` — which is
    `why-on-machine`, a CAPABILITY question answered with which machines could
    have run the step. A fine answer to a question the button does not ask:
    "here" is a position in TIME at least as much as on a lane. It now fires the
    blocker analysis.

    Three adjacent measured defects went with it. **(a)** A transport failure
    ("Failed to fetch") rendered as a chat turn in the testimony register,
    telling a planner the system had considered their question; it is now a
    connection notice with a retry and no register at all. **(b)** `cited_refs`
    fused the lanes an answer NARRATED with the alternatives it merely weighed,
    so two bars on CUT-01 reported four lanes, two at 0% utilisation — empty
    machines cited as evidence; `alternatives` is its own channel now (contract
    unchanged; an API response field, additive). **(c)** An order-level question
    resolved to the order's FIRST operation regardless of the board selection,
    which is how a question asked with ORD-000013 selected on PAINT-01 came back
    about CUT-01 with no bridging sentence; the selection carries `op_seq` now,
    only three operation-scoped intents read it, and an unscoped question SAYS
    which operation it answered about.


**§5a.39 — THE DOCUMENT CORPUS, IN TIERS, SHIPPED WITH THE BUILD (4B.15 Item 1).**
`modules/corpus.py` + `tools/build_corpus_index.py`. 512 passages over five
documents: **CURRENT** (docs/01, 05, 06 — 83), **HISTORICAL** (docs/04 — 340),
**INTENT** (docs/07 — 89). Three boundaries, all enforced in CODE rather than
requested of a prompt:

- **NO PURPOSE REACHES docs/07.** `TIERS_FOR_PURPOSE` does not list the INTENT
  tier, so a capability claim cannot be grounded in what we INTEND to build. A
  test asserts every purpose, not just the ones that exist today.
- **docs/04 IS OPT-IN AND EVERY PASSAGE IS DATED.** It carries SUPERSEDED
  rulings as first-class text — R-SC3(2)'s earliness price is present both as a
  landed ruling and as a retired one — so a retriever taking the first match
  states a retired mechanism as current WITH A REAL CITATION. Reachable only
  from `Purpose.DESIGN_RATIONALE`, and every passage renders as
  `[history, YYYY-MM-DD — may be superseded]`.
- **FAIL-CLOSED DATING COSTS THE FOUNDING DECISIONS.** 15 sections were DROPPED
  at index time for having no extractable date — the `D-nn` original decision
  log. The rule is that every historical claim is dated, so an undatable one is
  unservable rather than served bare. Reported in `dropped_undated`, asserted.

**CURRENCY IS A BUILD-TIME CHECK, NOT A PROMISE.** `docs/` is deliberately NOT in
the runtime image (the Dockerfile copies it into the TEST stage only and says
so), so a corpus reading `docs/` at runtime would be EMPTY in production rather
than merely stale — a worse failure and a silent one. The index is package data
at `src/mre/corpus_index.json` carrying a sha256 per source document, and
`tests/test_corpus.py` re-fingerprints the live `docs/`. Editing a spec without
rebuilding is a RED TEST. **EXCLUDED AND REPORTED** (`EXCLUDED_INTERNAL`, five
entries with reasons): close-outs, CLAUDE.md, docs/00/02/03/08, handoffs and
promotion dossiers, recon/scratch/spike output. Admitting any of it is a ruling
someone makes once, on purpose.

**§5a.40 — A MATCHED ROUTE COULD NOT BE WRONG (4B.15 Item 2).** Measured, FIVE
CONSECUTIVE TURNS were swallowed by the capability-coaching route, one of them
an EXPLICIT CORRECTION reparsed into the same wrong intent. Once the parse named
an intent above the confidence floor, that route's canned copy shipped whatever
it said — which inverts R-AI5, since tier one over-claims and tier two is never
reached. Synthesis OUTPERFORMED the routes everywhere it was allowed to run.
`modules/route_falsifiability.py` checks the DETERMINISTIC template rendering at
the dispatch seam, before any LLM render, and falls through to synthesis on:
**SUBJECT SILENCE** (the parse resolved a subject the answer never names) or a
**DISCARDED DISJUNCTION** (the answer surfaces neither alternative). The
alternatives carry the question's own preposition, so "that OPERATION'S routing
line" — which contains the fact without surfacing the choice — is a fall-through
rather than a pass. **IT CAN ONLY REJECT THE ROUTE THE PARSE CHOSE**; it can
never name one, and rejection has exactly one destination, so no deterministic
classifier returns. Fails OPEN in every direction.

**§5a.41 — THERE WAS NO ROUTE THAT READS A DECLARED FIELD (4B.15 Item 3).** "is
ORD-000013 op20 splittable" returned capability documentation with a scold and
"how long does op20 take" returned the order card — both fully specified, both
answered from the same snapshot by the blocker analysis one exchange later. The
facts were loaded; nothing asked for them. `Intent.ATTRIBUTE_LOOKUP` +
`modules/attribute_lookup.py` (parse prompt **v12**). The rule is deliberately
broad: **ANY declared field on ANY entity is askable, verbatim, with its
source**, and the field vocabulary is built by REFLECTION over
`contracts/entities.py` so a field added to an entity is askable the day it
lands. What is authored is the alias map, which authors WHICH FIELD to read and
never a value. **THE PROVENANCE CHAIN IS WALKED**: an Operation's `splittable`
is `derived`, so the answer cites the OperationSpec's `observed` source — the
submission column where the value entered the system. NOT DECLARED and DECLARED
AS ZERO render differently, always. **LIMIT, NAMED:** the second tier still
cannot read a field (the toolbox has no attribute reader), so a field question
the parse sends to synthesis is answered honestly and uselessly.

**§5a.42 — THE REPEAT DETECTOR WAS INVERTED, AND IT SCOLDED (4B.15 Item 4).** It
fired four times measured — on a DIFFERENT question, on an EXPLICIT CORRECTION,
on a factual lookup and on the demo opener — with **ZERO true positives**, and
it escalated: "Still the same; nothing has changed since you asked" is the
product blaming the planner for its own deafness. The counter measured MY OUTPUT
(how recently this route answered) and read it as THEIR INPUT. Split in two:
`repeat` requires the SAME question (terse re-ask behaviour, never a rebuke);
`deaf` requires the same delivered ANSWER for a DIFFERENT question, and answers
with self-doubt plus an offer to narrow. **THE SIGNAL IS THE OUTPUT, NOT THE
ROUTE** — two questions reaching one route and getting two good answers is the
route working, which the old counter could not distinguish and always got wrong.
A test forbids the scolding class of wording. **LIMIT:** it fires when the one
answer is CORRECT (three phrasings of one question), which is humble rather than
wrong but is not free.

**§5a.43 — CAPABILITY CLAIMS GROUND IN docs/05 OR ARE REFUSED (4B.15 Item 5).**
"can two machines share one operator" came back a confident YES describing
ALTERNATES, carrying `[synthesis — my reading, no record states this]` — on a
board where the blocker analysis was simultaneously and correctly reporting
B3/B5 operator pools among the families it does not weigh. **LABELING IS NOT
SUFFICIENT WHERE THE CLAIM IS WHAT THE PRODUCT CAN DO**: every other synthesis
claim is a reading of the board and a planner who distrusts it can look at the
board; a capability claim is acted on by AUTHORING DATA that is then silently
ignored, and there is no board to check that against.

`modules/constraint_catalog.py` parses docs/05's own MARKDOWN TABLES into **26
CatalogItems, 6 locked rulings and 6 global exclusions**. That is not retrieval
reading prose — a table is structure, and docs/05 §0 says the catalog is
"structured records first; prose is rendered from them". **THE PROSE-LOCKED DEBT
IS DISCHARGED FOR THE CATALOG ROWS**, not for the prose, which is quoted
verbatim and never parsed for meaning. The honesty register is **DERIVED** from
(verdict, status) — nobody authors "this one is aspirational" beside a row, and
moving a status column in docs/05 changes every answer about that item. A MIXED
status (B7/B8 is literally `PP (single-attr) / UI (multi-attr)`) gets its own
register rather than being flattened in either direction. Two new synthesis
tools (`constraint_catalog`, `spec_lookup`) put the same ground under the second
tier; synthesis prompt **v3** rule 9 makes reaching for them mandatory before a
capability claim. **AGREEMENT WITH THE BLOCKER ANALYSIS IS ASSERTED, NOT HOPED
FOR** — `UNCOMPUTED_FAMILIES` is the source of the not-weighed sentences, so the
two surfaces cannot drift. **THE TOPIC MAP'S ORDER IS LOAD-BEARING**, and it bit
in the same session: with `calendars` ahead of `time_windows`, "restrict an
operation to the day shift only" answered "Yes, proven end to end" about C1/C2
when the item is C4 (model-proven, §8 doorway) — the optimistic direction to be
wrong in, caught by a test that now pins it.

**§5a.44 — THE MODEL TIER, MEASURED — AND THE ASK PATH COULD NOT RUN ON TWO OF
THE THREE (4B.15 Item 6).** Both governed call sites hardcoded `temperature=0`
— correct on Haiku and a **400 on Claude Opus 5 and Sonnet 5**, which removed
the sampling parameters. Every request to both candidate tiers failed at the
transport before any answer existed to grade, so the tier question was not
merely unanswered, it was **unaskable**. `modules/llm_compat.py` sends a
sampling parameter only where the model accepts one, disables thinking on
thinking-by-default models (both call sites want one short structured emission,
and `max_tokens` caps thinking PLUS text), and carries a
retry-once-without-the-field fallback so a model family released later degrades
to a working call rather than taking the ask path down.

`tools/model_tier_bench.py` runs a 15-question bank through the FULL ask path,
scored deterministically (an LLM judge would make it circular) with MEASURED
token counts:

| tier | model | correct | fact | multi-hop | median s | $/question |
|---|---|---|---|---|---|---|
| haiku | claude-haiku-4-5 | 13/15 | 10 | 4/8 | 1.9 | 0.0211 |
| sonnet | claude-sonnet-5 | 14/15 | 12 | 7/8 | 4.4 | 0.0749 |
| opus | claude-opus-5 | 14/15 | 10 | 7/8 | 5.2 | 0.1248 |
| **split-hs** | **haiku + sonnet** | **14/15** | 10 | **7/8** | **1.5** | **0.0470** |

**RECOMMENDATION: KEEP THE PARSE ON HAIKU, MOVE SYNTHESIS TO SONNET 5.** Ties
best correctness and multi-hop, LOWEST median latency of all four (the parse
runs on every question; only synthesis-bound ones pay Sonnet), 37% under
Sonnet-everywhere and 62% under Opus-everywhere. **OPUS 5 IS NOT RECOMMENDED ON
THIS EVIDENCE** — 2.7x the split, better on no quality column, and it produced
the bench's only fully-fabricated answer (four machine names, three of which do
not exist, with ZERO tool calls; claim verification labelled every sentence as
unsupported and the falsehood shipped anyway). **THE SELF-CORRECTION MATTERS:**
the hypothesis that `llm_compat`'s disabled thinking caused it was TESTED and
REFUTED — a re-run with the identical setting called tools and answered
correctly. The failure is stochastic. **CAVEATS THAT MUST TRAVEL:** one run of
15 questions, so a one-or-two-question difference is noise (cost and latency are
not); the bank is narrow because 9 of 15 questions are now answered by
DETERMINISTIC assembly, which is itself the finding; the rates are a constant in
the tool. **THE DECISION IS DARYN'S — nothing shipped changed, both layers still
run Haiku.**

> **DECIDED AND SHIPPED, 2026-07-29 (Errand 4B.15a, §5a.46).** The
> recommendation above was ruled: synthesis constructs on `claude-sonnet-5` and
> the parse stays on Haiku, so the closing sentence "nothing shipped changed" is
> the state on 4B.15's evening, not the state now. **The table above is ALSO the
> first of two runs, not a settled measurement** — re-running the identical bank
> against the identical world moved every quality column and inverted the
> ranking (§5a.46). Read the `correct` / `fact` / `multi-hop` figures here as one
> sample; read the cost column, and "Opus is dearest, slowest and best at
> nothing", as the two findings that reproduced. The figures are left standing
> rather than rewritten — they are the first half of the comparison.

**§5a.45 — A TRUE FACT ABOUT THE WRONG DAY (4B.15 Item 0).** 4B.14's close-out
is CORRECT: PAINT-01 is OPEN on Tue 2026-01-13 (07:00-19:00, no closure) and
carries ZERO work. The live synthesis answer's "ran continuously from 07:00 to
11:24" is real, contiguous PAINT-01 occupancy — on Tuesday **2026-01-06**, the
other Tuesday in the window (ORD-000038 op30, ORD-000002 op20, ORD-000012 op30,
back to back, ending at exactly 11:24). **THE FAULT IS DATE RESOLUTION AND
NOTHING TOLD THE MODEL WHAT DAY IT WAS** — neither governed prompt carried a
reference date, a horizon or a weekday mapping, and the horizon spans five
Tuesdays, so "Tuesday" bound to the first one in the tool result. The blocker
analysis reasoned correctly about Jan 13 in the same session because it COMPUTES
with dates and never reads a weekday off a row. **IT DOES NOT WEAKEN 4B.14's
CHAIN**, which was re-verified end to end from the snapshot (431 working minutes
needed, 294 left after op10 ends 14:06, Wednesday a maintenance closure, op20
running Thursday 07:00-14:11 = 431 exactly). FIXED: `render_calendar` puts the
reference date and horizon into the shared context block and synthesis prompt
rule 10 forbids taking a weekday from whichever row appeared first.

**§5a.46 — LATENCY IS THE COLUMN THE BENCH SUMMARY DROPPED (Errand 4B.15a).**
4B.15 recorded per-question latency and its summary carried only the MEDIAN, and
no report JSON was persisted — so the p90 could not be recovered from that
session at all, and the tier decision was taken without it.
`tools/model_tier_bench.py` now carries `p90_latency_ms` in the summary and the
table so this cannot recur. Nearest-rank on 15 rows: the p90 IS the 14th-slowest
question, an actual question that actually happened, not an interpolation.

RE-RUN, 2026-07-29, same bank, same pinned world, same tool:

| tier | model | correct | fact | multi-hop | false | median s | **p90 s** | $/question |
|---|---|---|---|---|---|---|---|---|
| haiku | claude-haiku-4-5 | 14/15 | 11 | 7/8 | 0 | 2.1 | **14.6** | 0.0224 |
| sonnet | claude-sonnet-5 | 14/15 | 12 | 7/8 | 0 | 2.4 | **21.3** | 0.0673 |
| opus | claude-opus-5 | 10/15 | 9 | 3/8 | 1 | 5.8 | **37.7** | 0.1150 |
| **split-hs** | **haiku + sonnet (SHIPPED)** | 13/15 | 11 | 6/8 | 0 | 2.3 | **23.1** | 0.0420 |

**THE P90 IS MATERIALLY WORSE AND THE ASK PANEL IS INTERACTIVE.** The shipped
split's tail is +8.5s (+58%) over Haiku-everywhere while the MEDIAN barely moves,
and the gap between those two columns is the whole finding: most questions are
answered by a deterministic route after a fast parse and are untouched by the
tier change, while every question that reaches the second tier now waits on a
bigger model. Measured live, end to end, on the shipped defaults — contracted
routes **1.7s**; synthesis **9.9 / 16.2 / 18.1s**. So a demo that stays on
contracted routes feels identical and a demo that asks the open questions — which
is what the second tier is FOR — waits 10–20s an answer. **THE TAIL IS NOT THE
MODEL CLASS AND THE FIX IS NOT A CHEAPER MODEL:** every tier's p90 is 6–9× its
own median, including Haiku's, which is the second tier's multi-step tool loop. A
cheaper model runs the same steps faster; it does not run fewer. If interactive
feel becomes binding the lever is streaming the first beat or running the loop in
the background.

COST, measured tokens × published per-MTok rates (only as current as the `TIERS`
dict in the tool): Haiku-everywhere **$2.24**, THE SHIPPED SPLIT **$4.20**,
Sonnet-everywhere **$6.73**, Opus-everywhere **$11.50**, per 100 questions. The
split is +2¢ a question over what shipped before it (+88% in ratio) and **38%
under Sonnet-everywhere**, because the parse runs on every question and only the
synthesis-bound ones pay Sonnet. 4B.15 measured 37%; the two runs agree.

**THE QUALITY RANKING DID NOT REPRODUCE, AND THAT MUST TRAVEL WITH THE
DECISION.** Between two runs of the same 15 questions against the same world:
Opus fell 14/15 → 10/15 and produced this errand's one forbidden falsehood; Haiku
ROSE 13/15 → 14/15; the shipped split FELL 14/15 → 13/15, **below
Haiku-everywhere on this run**. §5a.44 said a one-or-two-question difference is
inside the noise; two runs say something sharper — on a 15-question bank the
quality ranking is **not stable at all**, and the only columns that reproduced
are cost (same ordering, within 10% on every tier) and the finding that Opus is
slowest, dearest and best at nothing. What survives both runs in Sonnet's favour:
it reached the most facts of any tier in BOTH (12, against Haiku's 10 then 11)
and never produced a forbidden falsehood in either. **The honest statement is
"the bank can resolve the cost, not the quality difference" — not "the split is
measurably more correct."** A tier decision that wants to rest on correctness
needs a bigger bank or repeated runs; the instrument for that is the r5 bank at
~30 graded questions, which is queued and has never been run (§5a.7, §5a.22).

**§5a.47 — A SYNTHESIS ANSWER THAT READ NOTHING DOES NOT SHIP (Errand 4B.15a,
`modules/ungrounded_guard.py`).** THE SPECIMEN is §5a.44's: Opus, asked which
machine carries the most work, named three machines that DO NOT EXIST in this
plant, with **ZERO tool calls**. Claim verification did its job — every sentence
was labelled unsupported — and **the answer shipped anyway**, because the tier's
contract is to LABEL what it grounds, not to withhold what it cannot. An answer
that read nothing and still names this plant's entities did not reason from
evidence; it recalled a plausible shape. Three conditions, all deterministic, no
model judgment anywhere: **(1)** the answer came from the SYNTHESIS tier; **(2)**
ZERO tool calls AND no cited record that RESOLVES against the evidence index;
**(3)** a delivered claim names something specific to THIS WORLD — an entity
identifier, money, an ISO date, a clock time — **that the planner did not put
there themselves**.

**CLAUSE (3) IS WHAT MAKES IT SAFE.** A token the planner typed is not the
tier's invention: an answer echoing "ORD-000013" back at the person who asked
about ORD-000013 fabricated nothing, so only tokens the tier INTRODUCED count. A
bare integer is deliberately NOT a world token ("two ways to read that" is prose,
not a claim about the plan). **CLAUSE (2)'s SECOND HALF IS WHAT MAKES IT
DODGE-RESISTANT:** a model that invents record ids alongside its machines gains
nothing, because the assembler resolves cited ids against the real index and
drops the rest — a fabricated citation is an empty list, not a free pass.
Attached at the ONE delivery seam both renderers share, beside the cost-proof,
sufficiency and coverage riders, and it is the only one there that **WITHHOLDS**
rather than qualifies: the defect is not an under-stated qualification, it is an
answer with nothing behind it. Fails OPEN in every direction — an odd bundle
shape, a missing count, an exception all deliver the answer untouched.

**THE NEGATIVE CONTROL IS THE TEST THAT MATTERS MOST:** a synthesis answer that
legitimately needs no tools STILL SHIPS. `TestNegativeControl` pins four — the
bench's weather floor (no answer in any evidence store, and the right response
reads nothing and says so), a general statement about the product's scope, a bare
count, and the no-claims honest floor. Without it the guard is a mute button on
the second tier, and the honest floor is the first thing a mute button eats.
**LIMIT, NAMED:** the guard is scoped to the synthesis subject type, so
`prove_it` — a second model surface at the same seam — is NOT covered. It re-runs
grounding on one existing claim and has a different failure mode; covering it was
not measured and is not assumed.

**§5a.48 — A CORPUS-GROUNDED CLAIM CANNOT CARRY A `[record:]` CITATION (Errand
4B.15a).** Measured live: asked whether downtime is set per machine or per
operation, the second tier answered CORRECTLY from docs/05's catalog rows and all
four of its claims landed **INTERPRETIVE** — `[synthesis — my reading, no record
states this]` — because the corpus and catalog tools return SPEC TEXT rather than
evidence records, so `claim_verifier` has nothing to re-fetch. The labels are
honest and the answer is right, and the surface still makes a
documentation-grounded answer read WEAKER than an inference over placements.
**THAT INVERTS THE EVIDENCE HIERARCHY THE PRODUCT IS BUILT ON**: a verbatim quote
of the constitution is the strongest ground available for a capability claim
(§5a.43 is the ruling that says so), and it is currently labelled with the
weakest register the surface has. The fix is a CITATION KIND for spec passages,
which is a contract change and therefore a reviewed vocabulary-class change — not
a relabelling. Until it exists, an answer whose strongest evidence is a spec
passage should route that reference through authored copy rather than let
synthesis carry it under the interpretive label.

**§5a.49 — THE COUNTERFACTUAL: WHAT WOULD HAVE TO BE DIFFERENT (4B.16 Item 1).**
4B.14's blocker analysis answers "what is holding this here" and answers it
well. The question that follows it — "so what would have to change?" — had no
route, and would have been swallowed by `swap-move` (which weighs a board move
between two orders and prices it in the sandbox) or `advice` (which is about the
plan, not one operation): the adjacent-match failure, both times, answering with
something a planner cannot act on. `what-would-change` joins the vocabulary
(parse prompt **v13**, `src/mre/modules/counterfactual.py`) as the INVERSE of the
blocker analysis **over the same computed bounds and no new ones**: take the
family that BINDS and report the change that would move it, with its threshold
and the arithmetic.

  * **EVERY THRESHOLD IS VERIFIED BY RE-RUNNING THE SAME SCAN.** A lever whose
    hypothetical does not actually move `earliest_fit` is DROPPED, not stated —
    which is what stops the route from being arithmetic about arithmetic.
  * **AND THE VERIFICATION APPLIES R-C3.** `earliest_fit` does not know the
    degenerate-split rule (its caller does), so the min_chunk lever verifies
    through `resumable_fit`, which does. The measured consequence: the brief's
    worked specimen proposes `min_chunk <= 240` and **240 does not work** — at
    216 the solver treats the operation as atomic again. The computed ceiling is
    **215 = floor(431/2)**, and that number came out of the check, not the copy.
  * **NECESSARY, NEVER SUFFICIENT — enforced by shape.** Every answer carrying a
    lever names the NEXT BOUND that would apply once the barrier is gone
    ("an earlier step [docs/05 A1/A2] at Tuesday 2026-01-13 14:06 — that removes
    the barrier; it does not place the operation there"). Where the binding
    family is not chunk-fit, the next bound is RECOMPUTED through the tail of the
    ladder rather than assumed to be the runner-up: relaxing precedence can
    expose a chunk-fit the runner-up never mentioned.
  * **THE B1 LINE IS COMPUTED, NOT STATED.** "431 contiguous minutes free on an
    eligible machine" is the brief's condition; the route resolves capability
    eligibility and scans each other lane from the SAME upstream floor (release /
    precedence / frozen / pin — the bounds a different machine is still subject
    to). On the pinned board PAINT-01 is the only eligible lane, and the answer
    says so rather than offering a door that is already shut.
  * **TWO THINGS IT REFUSES TO PRICE, both named on the answer.** B7/B8
    changeover (4B.14's precedent: the setup at another position depends on what
    would precede it there, which is a different schedule) and — on a `chose`
    verdict — the OBJECTIVE. A DECLARED CLOSURE standing in the way is reported
    and deliberately not priced: lifting a maintenance day would plainly move the
    operation, but saying what the machine's open hours would be on a day the
    calendar declares shut is an invention, not a reading.
  * Carries the `uncomputed` block verbatim from the blocker analysis. A
    counterfactual that ignores B3/B5, B7/B8, C4 and F3 is exactly as partial as
    the explanation was.

**STATED LIMIT: a planner-named DAY is not parsed.** "Can this move to Monday"
reaches the route, and the route answers about the target it COMPUTES — the
near-miss window / the next-earliest bound — naming the weekday and the date it
is testing. Resolving "Monday" to one of five Mondays is exactly the class
§5a.45 measured, and inventing a resolver for it was out of scope here.

**§5a.50 — THE OPENER: WHAT SHOULD I BE LOOKING AT (4B.16 Item 2).** `briefing`
was the 7am morning triage — late orders by lateness x priority, one
data-quality line — and it was a fraction of what the persisted document knows.
A board can be provably optimal, hold a maintenance day that pauses eleven
operations, run one machine near saturation beside eligible empty ones, and
carry fourteen orders beyond the horizon, and none of it reached the answer. The
other three ways a planner opens a board ("how does this schedule look",
"anything I should know", "what's the state of things") were shape reads that
rule 7 correctly sent to `unmatched`, where the second tier reasoned out an
answer the document could have TESTIFIED to.

`src/mre/modules/board_opener.py` builds every item the document supports,
**ranked by consequence**, each line carrying its own number and a POINTER to
the question that opens it up. Entirely contracted testimony; no synthesis on
the primary path.

  * **THE RANKING RULE IS STATED, because a ranking nobody can check is an
    opinion.** Band 1 is money at stake and its two members are COMPARABLE
    because both are currency: controllable tardiness (R-PD1 clause 4 — never
    the floor) and the unproved gap priced against the ledger (`total x gap`).
    Band 2 is work that will slip (at-risk, unplaced, closures) and ranks by
    count, band 3 is structure (concentration, certificate, undeclared derate),
    band 4 is CLEAN. Within a band the priced item leads — not because it
    matters more, but because it is the only one whose size is known.
  * **"THREE THINGS AND NONE OF THEM ARE ON FIRE" IS REACHABLE.** A proved
    optimum and an empty late list are REPORTED as band-4 reassurance, so a clean
    board gets a real answer instead of a silence a planner has to interpret.
  * **ELIGIBILITY IS WHAT MAKES CONCENTRATION A FINDING.** A machine at 88%
    beside two idle ones is a finding only if those machines could have taken the
    work; otherwise it is what a specialised cell looks like. Where capability
    could not be resolved, the read says so rather than reporting no
    alternatives.
  * **AT-RISK IS CONSERVATIVE BY CONSTRUCTION.** Slack is calendar minutes and
    the threshold is the order's own longest step in WORKING minutes, which is
    never more than the calendar time that step occupies — so every order flagged
    really does have less room than one of its own operations needs.
  * **WHAT THE DOCUMENT DOES NOT SUPPORT IS REPORTED, NOT OMITTED.** A monolithic
    run says it has no tray; a solve without the coarse zone says the coming
    weeks were not checked; an answer reached without a document says it is
    reading the evidence store alone. An opener that silently drops a category
    reads as a clean bill of health for it.

**MEASURED ON TWO REAL BOARDS** (`_data/runs`, unchanged): the pinned rolling
world returns four worries (2 at-risk, the Jan 14 maintenance day across 9
machines, 14 beyond the horizon, an undeclared derate) over two clean items; a
monolithic 40-order run leads with an unproved gap of **56.9% = up to 24,414.97
of a 42,895.47 ledger**, then 13 late orders at 20,701.25, then two
proceeded-past findings — ranked by money, largest first, as the rule says.

**CARRIED, NOT FIXED (4B.16):** the opener's certificate item reads the evidence
store's findings and CANNOT state the GRADE — the grade is a submission fact the
API joins on `/meta` and the schedule document does not carry it, so the one
figure a stranger recognizes ("ACCEPTED") is the one this item cannot say. The
Gatehouse recon (`RECON_GATEHOUSE.txt`, Q1) names the same seam from the other
side. Also: **concentration did not fire on either measured board**, because
demo density runs far below the 85% threshold — the item is unexercised live and
proven only by unit test, which is the same demo-density limit §5a.11 recorded
for the coarse zone.

**§5a.51 — BOTH 4B.16 ROUTES REACH A PLANNER'S PHRASING, AND THE MEASUREMENT
FOUND A LEAK IN THE INSTRUMENT (Errand 4B.16a Item 2).** Ten phrasings fired live
against the pinned `rolling-c362baa4-1b0`, each its own conversation, on shipped
defaults (parse Haiku, contracted routes, template render). **Nine of ten reached
the intended route.** `what-would-change` took `"what would have to change for
op20 to run Tuesday"` (0.92), `"how do I get this earlier"` (0.92),
`"can this move to Tuesday"` (0.92) and `"what if it were splittable"` (0.92,
binding `concept=splittable` off the utterance); `briefing` took all four cold
opens — `"what should I be worried about"`, `"how does this schedule look"`,
`"anything I should know"`, `"what's the state of things"` — at **0.95 each**.
Route latency median **1462 ms**, p90 2124 ms, zero retries, zero malformed
parses.

**THE ONE MISS IS A ROUTE BOUNDARY, NOT A GAP, AND IS NOT FIXED.**
`"why can't it be earlier"` resolved to **`why-here` at 0.95 with
`polarity=negative`** and answered correctly — the couldn't-verdict with the
family ladder. That is defensible on its own terms: `what-would-change` is
DEFINED as why-here's inverse over the same computed bounds (§5a.49), so a
"why can't" utterance sits exactly on the seam, and the negative polarity is the
parse doing what it was built to do. Whether the two should merge is the
vocabulary question **4B.14 already declined to rule on** for `start-reason`
versus `why-here`; widening either meaning to capture this phrasing was
explicitly out of scope. The reverse-facing note matters more: the errand's own
prior evidence had `"how do i change that"` — four words, no subject — reach
`what-would-change` off board selection, so the prompt is NOT thin on cold opens.
It is precise on a seam.

**THE ADDED CASE: A PRONOUN AFTER A WHOLE-BOARD READ HAS NOTHING TO BIND TO.**
`"how do i fix that"` following a `briefing`, nothing selected, parsed as
`remediation` / `followup=deepen` / **`clarify=no-subject`** at 0.72 and asked
which order or machine was meant. Honest, and the right floor: the resolution
ladder is card > selection > last answer > history, and a briefing's "last
answer" is the whole board — the four ranked items name several orders and no
single subject. The contrast with the same follow-up after a `why-here` (which
binds from selection) is the finding: anaphora works where the prior turn had ONE
subject and correctly refuses where it had many. The mitigation already shipped is
the opener's own per-item pointers ("-> Ask ..."), which is what a planner should
click instead.

**THE INSTRUMENT WAS CONTAMINATED, AND IT WOULD HAVE BEEN READ AS A PRODUCT
DEFECT.** The first run of this bank opened **seven consecutive turns** with
"I've now given you this same answer for two different questions, which probably
means I'm not understanding what you're asking" — each citing a question from a
conversation the bank had already thrown away with `RESET`. Cause: the deafness
signal's memory (`interpreter._DELIVERED`) is module-level and keyed by session
id, because a delivered ANSWER cannot be read off the history channel, which
carries only question and route (§5a.42's whole point). `RESET` cleared history,
selection, last-answered and the card — four channels — and **missed the fifth**.
`forget_deliveries(session_id)` is the symmetric clear for `remember_delivery`
and the exam runner's `RESET` now calls it; re-run, the rider fires zero times
and the phrasing table above is the uncontaminated one. Pinned in
`tests/test_route_falsifiability.py`, including an assertion at the runner's own
call site, because a RESET that clears four of five channels poisons every bank
that starts a second conversation — which is most of them.

**REPORTED, NOT FIXED — the product half of the same rider.** Four different
phrasings of the opener inside ONE conversation legitimately trip the rule (same
answer, different questions) and the second one would open with self-doubt. That
is §5a.42's known limit ("distinguishing 'one answer because I am confused' from
'one answer because it IS the answer' needs a signal this session does not have")
and it now lands on the FIRST THING A STRANGER READS, which raises its severity
without changing its shape. Two mitigating facts, both verified rather than
assumed: the REPL passes no `session_id`, so the detector is inert there; and the
cockpit has no conversation-clear gesture at all (`#ask-clear` clears the board
highlight), so no product surface currently leaks across a boundary.

**§5a.52 — THE OPENER'S SCAN IS 4% OF THE TURN; THE PARSE IS THE REST (Errand
4B.16a Item 3).** Measured on the pinned world, dispatch only (assemble +
template render, parse excluded, 12 samples after a warm call):
**`what-would-change` 7.3 ms** median, **`briefing` 61.0 ms**. Of the opener's
61 ms, **58.7 ms is the scan** and effectively all of that is `_opener_load`
(59.0 ms) — which walks `_open_windows` for all 15 machines across the whole
horizon; every other extractor is under 4 ms and `_opener_late` /
`_opener_certificate` are under 0.1 ms.

**PRECOMPUTE, ANSWERED BOTH WAYS AND LEFT.** With the opener cached, the same
dispatch is **0.4 ms** — precompute removes 99% of the dispatch and **4.6% of a
parse+dispatch turn**, because the parse is one live model call at a 1251 ms
median. So it is not worth a contract change at this density, and no contract
change was made. **The shape it would need, named for whoever revisits it:** an
Optional block on the schedule document (the `RollingBlock`/annotations pattern
the coarse zone already uses — absent on an older document, present with its own
provenance), minted at registration where the document is assembled. **The reason
to revisit it is scale, not this number:** `_opener_load` scales in machines x
horizon days, and the pilot volume named in CLAUDE.md is 174 workcenters against
the 15 measured here — at ~12x the machines the scan plausibly becomes the
dominant term rather than 4% of it, and pilot-volume latency is UNMEASURED for
every figure in this repo.

**§5a.53 — THE COUNTERFACTUAL'S SPEC CITATIONS DODGE §5a.48 DELIBERATELY, AND
THAT IS NOW STATED WHERE A REFACTORER WILL READ IT (Errand 4B.16a Item 3 A3).**
Confirmed: `counterfactual.SPEC_OF` is a dict of AUTHORED CONSTANTS
(`"docs/06 §5.3 routing_lines.csv splittable / min_chunk_minutes"` and five
siblings) rendered by the template as part of each lever line, so the reference
never passes through synthesis and never takes a claim label at all. The dodge
complies with §5a.48's own closing prescription — "an answer whose strongest
evidence is a spec passage should route that reference through authored copy
rather than let synthesis carry it under the interpretive label" — which was
written by Errand 4B.15a, **one commit before** the route existed.

**But it was deliberate at the RULING level and incidental at the ROUTE:**
4B.16's close-out does not mention §5a.48, and nothing in `counterfactual.py`
said why those strings are hardcoded. Reading them out of the 4B.15 corpus index
instead would look like a tidy-up — the index ships with the build, sha256 per
document — and would silently re-open §5a.48 for this route by turning each
reference into a corpus-grounded claim wearing the weakest label the surface has.
The prohibition is now recorded on `SPEC_OF` itself, which is a comment and not a
behaviour change. **THE SPEC-CITATION KIND IS STILL OWED**, unchanged in scope:
it is owed for the SYNTHESIS tier, where §5a.48's measured specimen lives (four
correct claims quoting docs/05, all four `[synthesis — my reading, no record
states this]`), and therefore for every answer whose ground is
`constraint_catalog` or `spec_lookup` rather than a placement. Contracted routes
carrying authored copy are the exception that works around it, not a discharge of
it.


**§5a.54 — THE r5 BANK IS CALIBRATED, RUN AND GRADED; §5a.22 IS DISCHARGED
(Session 4B.17).** Committed 4B.5, carried unrun for six sessions, expectations
invalidated three times. Recalibrated against the pinned world's PERSISTED
document under four rules — the question text of all 27 original specimens
UNCHANGED, every expectation change logged in `tests/ai_exam/RUBRIC.md`'s
append-only RECALIBRATION LOG with its cause and its old text, no expectation
copied from output (the bank was recalibrated BEFORE its first run, so there was
none to fit to), and anything underivable marked UNGRADED with a reason. Six
specimens added verbatim (two of the brief's eight were already banked); 27 → 33
questions. Ran **six times** — three on shipped defaults (parse Haiku /
synthesis Sonnet 5) and three on Haiku-everywhere — 198 answers.
**THE ONE WORLD FACT THAT MOVED THE MOST EXPECTATIONS: nothing is late on this
board** (all 26 placed demands early, worst slack ORD-000011 at 502 min,
tardiness $0.00, bound closed). Nine of the bank's questions are about lateness,
so every one became a false-premise specimen graded on 4B.13's premise
correction. **THE CARD WAS RE-DERIVED AND THE SPECIMEN DEGENERATED:**
`runner.py`'s constants are now the committed fixture's (+$32.20 = reopt $0.00 +
move +$32.20, affected set EMPTY), and because 4B.7 made `reopt_delta_abs` 0.00
BY CONSTRUCTION (§5a.12) the 4B.6a specimen "what did the move itself cost, not
the re-solve" **CANNOT DISCRIMINATE** — move equals total on every card the
product can produce. Reported as unexercisable, never counted as a pass.
**A BANK AUTHORING BUG FELL OUT:** the no-card turn carried
`EXPECT route=open-card` directly beneath a comment forbidding exactly that, so
a run would have graded the defect as the pass; removed, and that turn is
hand-graded because EXPECT cannot express a negative. **RESULT: 5 truth
failures, 4 expectation drifts, 10 conversational misses; 32 of 33 questions
STABLE across three runs on shipped defaults, 33 of 33 on Haiku.** Narrative and
every verbatim answer in `docs/closeouts/4B.17.md`. **NOTHING WAS FIXED** — a fix
bundled into the session that found it cannot be attributed, and R-AI4 gives the
felt-bar call to Daryn.

**§5a.55 — THE PINNED EXAM WORLD CANNOT STATE ITS OWN COST PROOF, AND SIX
SESSIONS OF AI MEASUREMENT RAN ON IT (4B.17, TRUTH FAILURE A4).** Same world,
same `runs/` directory, same route, two answers: a LOADED evidence index gives
"I can't tell you — this schedule carries no solver report I can read", a
REBUILT one gives "Yes — and this is proved, not asserted." The document beside
both says `OPTIMAL`, `gap 0.0`, and the strip reads that record and says PROVED —
so **the strip and the answer surface disagree, which is the precise failure
§5a.23 was discharged to prevent**, re-opened underneath it.
**MECHANISM: `EvidenceIndex.save()` persists `entity_records`, `finding_index`
and `run_registry` only, and `load()` rebuilds `_all_evidence` from
`entity_records` alone** — so the M6 `solve_complete` Event, which is RUN-level
and has no entity subject, does not survive a save/load round-trip and
`cost_proof.from_evidence` returns `no_solve` on any loaded index. Measured: the
pinned target's 114 KB index contains "solve_complete" **zero** times while its
own `runs/58d67288-….jsonl` contains it twice. **BLAST RADIUS — AND PRODUCTION
IS AFFECTED, ON THE MONOLITHIC PATH.** `_execute_solve` (`api/app.py:877`) runs
the monolithic pipeline by calling `mre.__main__.main`, whose M9 step saves the
index at `__main__.py:585` on the SUCCESS path — as does `demo.py:244` — and
`api/app.py:1482` prefers a persisted index when one exists. **Seven of the
fourteen solved runs in this repo's `_data/runs/` carry one, and all seven are
monolithic.** The ROLLING path is the exception (`_execute_rolling_solve` never
goes through `__main__`), which is why the four `snap-rolling` runs have no index
and why 4B.13 measured the right answer through `/ask`. The pinned exam world is
rolling but its BUILDER saves one (`build_rolling_exam_run.py:384`), so six
sessions of AI measurement ran on a board that cannot state its own cost proof.
**THE WORST CONSEQUENCE IS THE OPENER'S BAND 1.** Measured on the real monolithic
run `_data/runs/7f97d9d1-…` (document: `FEASIBLE`, gap **0.5692**, ledger
51,637.18): loaded, the briefing offers **3 things**; rebuilt, it offers **4**,
and the new one ranks **SECOND, in band 1** — *"The cost optimum is NOT proved …
that bound leaves up to **29,390.52** on the table"*. So on every monolithic
board the API serves, the money member of band 1 is **silently absent**, the
"Not covered by this read" section does not mention it, and `_proof_items`
returns `[]` on `no_solve` so neither the unproved nor the proved branch can
fire. **AND §5a.23'S MONEY RIDER CANNOT FIRE EITHER** — it is gated on
`unproved`, which is False on a `no_solve` proof, so a money answer on a
56.9%-gap board volunteers nothing about the gap. **NOT FIXED:** persisting
run-level records changes a persisted format and dropping the load-if-exists
preference changes API behaviour; either is a ruling. No bank question asked for
this — it was found while deriving the briefing's expectation, and the first
reading of its blast radius (that production was unaffected) was WRONG and is
corrected here.

**§5a.56 — THE MERGED SPAN IS THE SYNTHESIS TOOLBOX'S `duration_minutes`, AND
ITS `busy_minutes`: THE FOURTH SEAM OF A DEFECT CLASS FIXED THREE TIMES (4B.17,
TRUTH FAILURE A3).** Queried directly against the pinned snapshot:
`placements_for_order` and `placements_for_machine` report ORD-000011 op10 as
`"duration_minutes": 5821.0`, and `machine_occupancy` reports
`"busy_minutes": 5821.0, "gap_before_minutes": 0.0`. The truth is **1501 working
minutes in three chunks across a 5821-minute span**, 4320 minutes of which are
nights and a weekend when CUT-01 is closed and the operation is paused — the
exact figure 4B.13 Item 0 fixed and the reason 4B.14 split the job card into
separate RUN TIME and ELAPSED SPAN rows. **`busy_minutes` is the worse half:
CUT-01's total OPEN time between those timestamps is 1501 minutes, so 5821
exceeds the machine's entire capacity in that span by 3.9x**, and
`gap_before_minutes: 0.0` denies a pause the operation contains. **THE MODEL IS
NOT THE FAULT** — there is no run-time figure anywhere in those rows, so a
reasoner has nothing truer to quote; the answer that carried it cited a real
record and the verifier passed it VERIFIED, correctly. Observed live in 2 of 3
Haiku-everywhere runs and absent from the Sonnet runs only because those turns
did not call the tool. CLAUDE.md's own rule names the class: **a defect class
fixed at one seam is not fixed** — 4B.13 fixed two, 4B.14 found a third at
`_load_enriched_assignments`, and the synthesis toolbox is the fourth, unchecked
because it is not on the board. **NOT FIXED:** the tool surface is a governed
artifact and this wants the session that closes the class, not a patch.

**§5a.57 — 33 QUESTIONS x 3 RUNS STILL CANNOT RESOLVE THE TIER, AND THIS TIME
THE REASON IS STRUCTURAL (4B.17 Item 4).** Both configurations, same bank, same
world: truth failures 3 distinct / 9 firings (shipped) against 4 / 11 (Haiku,
the extra being §5a.56's, which is the tool's); asked fact reached 31/31/31
against 31/31/30; multi-hop 8/8/8 against 8/8/7; median latency over all turns
**1441 ms** against **1477 ms**, p90 **3586** against **3135**; contracted median
1415/p90 3012 against 1444/2777; synthesis median/p90 **6189 / 23108 ms (n=5)**
against **10269 / 15353 ms (n=6)**; cost per question **$0.0105** against
**$0.0110**. **THE VERDICT: THE BANK CANNOT RESOLVE IT, AND THE REASON IS THAT
31 OF 33 QUESTIONS NEVER REACH THE LAYER THE SPLIT CHANGES.** Everything else
routes to contracted templates whose render is byte-identical under both
configurations; the tier's whole surface here is two questions, one of which is
the unanswerable floor in both — so the measurable surface is **one question,
six times**, and across all 198 answers the two configurations differ in exactly
**one** routing decision, which is the PARSE's, and the parse is Haiku in both.
**§5a.46 named a bigger bank as the instrument for the quality column; this bank
is bigger and it is the WRONG KIND of bigger** — a founder-regression bank is
contracted-route regressions by design and is therefore nearly blind to the
second tier. The instrument for a tier decision is a bank whose questions are
UNMATCHED by design. **What did reproduce:** cost is a coin flip at 5% apart and
**Sonnet is the cheaper of the two here**, because Haiku-everywhere spent 21%
more input tokens (1.01M vs 0.83M) over 12 more calls — §5a.46's shape with the
sign flipped, the second tier taking MORE steps rather than the same steps
faster. **NO TIER CHANGE IS RECOMMENDED; the numbers are recorded and the
decision is Daryn's.**

**§5a.58 — THE `repeat` / `deaf` BOUNDARY IS KEYED ON STRING IDENTITY, SO A
REPHRASED RE-ASK GETS SELF-DOUBT (4B.17, C2/C3).** Measured 6/6 on two turns.
"how many are late again" after "how many orders are late", and "how many
machines" after "how many machines are there", both get *"I've now given you
this same answer for two different questions, which probably means I'm not
understanding what you're asking"* plus the FULL recitation again plus an offer
to name a field. Two firings, zero true positives — the same score §5a.42
recorded for the pre-split detector, on the other side of the split. **THE
CONTRAST IS THE FINDING:** the same string twice (`what should i do`, twice
running) gets the CORRECT lead, "Same answer as a moment ago —", over a
byte-identical body. So `repeat` fires on identical text and `deaf` claims every
rewording, which means the bank's C(c) terseness specimen — a count re-asked
answers tersely — **never gets to fire at all**. §5a.42's named limit
("distinguishing 'one answer because I am confused' from 'one answer because it
IS the answer'") is now measured live rather than anticipated. NOT FIXED: keying
`repeat` on the question's MEANING needs the signal §5a.42 already said this
work does not have.

**§5a.59 — §5a.51's "off board selection" CLAIM DOES NOT REPRODUCE (4B.17, drift
B4).** §5a.51 records `"how do i change that"` — four words, no subject —
reaching `what-would-change` off a board selection. In a cold conversation
carrying ONLY `SELECT order=ORD-000013 machine=PAINT-01` and no prior turn, it
parses **`unmatched` at all six runs** and falls to the synthesis floor with the
subject unbound, whose offered doors are then "show every late order" and "list
the data-quality problems" — unrelated to the order the planner had selected,
which RUBRIC entry 6's RESOLVED ruling makes a C5 failure by name, on a board
with no late orders. Either the errand's turn carried a prior answer its note
does not mention, or a bare selection does not carry an anaphor. **Reported, not
chased — the note as written is wrong and correcting it is a fix.**

**§5a.60 — TWO AUTHORED DOOR LABELS ASSERT FACTS ABOUT THE BOARD WITHOUT READING
IT (4B.17, TRUTH FAILURE A1).** `ask_fallback_copy.ROUTE_OFFERS["machine-idle"]`
(`ask_fallback_copy.py:58`) is the string *"explain why {machine} carries no
work"*, and the table's own header says the slot is "filled from the
interpreter's partially-resolved params where present, else a generic noun" —
no read of the board enters it. Asked "would overtime on CUT-01 help", the product offers, three lines
apart, to *"show what's running on CUT-01"* and to *"explain why CUT-01 carries
no work"* — **CUT-01 carries 18 of the 56 bars and is the busiest machine in the
plant.** Same table, same class, not fired in this sweep:
`"advice": "explain why each order is late and price a what-if move"` on a board
where nothing is late. **A door label is not a question, it is a claim**, and the
registry's reverse-guard (`tests/ai_exam/test_real_doors.py`) proves each probe
PARSES to a live route — a door that opens — and never that the room behind it is
furnished. The same gap is why §5a.61's trailing offer routes to a null answer.
NOT FIXED.

**§5a.61 — THE COACHING INVITATION CANNOT DECLINE TO FIRE, BY SHAPE (4B.17 Item
5(a)).** `INVITE_COACHING` (`ask_fallback_copy.py:532`) is registered with
`slots=()`. `invitation_line()` returns None only when a required slot is
missing, so **a pattern with no slots can never withhold itself and can never
vary** — and it is fired from both coaching branches (`renderers.py:1405` and
`:1419`), so every coaching answer carries *"Want to check what the submission
already declares? Ask 'what data problems exist?'"* whatever the subject.
Confirmed live 6/6 on the overtime turn. On the pinned board that question
returns a clean submission, so the offer sends a planner who asked about
overtime to a null answer about something else. **A COMPUTED OFFER NEEDS THREE
THINGS the machinery does not have:** a slot (so there is something to fill or
withhold on), a read of whether the door has anything behind it (§5a.60's gap),
and a per-capability target — the useful follow-up after "how do I declare
overtime" is what THIS submission declares for it (`calendars.csv` exception
rows, `overtime_premium_multiplier`), which is `attribute-lookup`-shaped and
therefore vocabulary-adjacent. REPORTED, NOT BUILT.

**§5a.62 — THE BINDING-FAMILY CENSUS IS NOT DERIVABLE FROM THE PERSISTED
DOCUMENT, AND IS EMPTY ON THIS BOARD ANYWAY (4B.17 Item 5(b)).** "How often does
each resource appear as the BINDING family across late orders" has **zero rows on
the pinned world** — nothing is late — the same demo-density limit §5a.11
recorded for the coarse zone and 4B.16 for concentration. And it is not
derivable from the document alone: of the seven reads
`Explainer._blocker_inputs` assembles, contract 1.11's document carries open
windows and closures (`resources[].calendar_windows` with a `kind`) and chunk
occupancy on the primary lane (since 4B.13), but **NOT splittability or
min_chunk** (`AssignmentBlock.splittable` / `min_chunk_min` are contract **1.12**
and Optional; this board is 1.11), **NOT precedence or release for committed
work** (`interaction.precedence_edges` holds THREE edges and
`interaction.operations[].earliest_start` covers only the 11 ACTIVE-window ops,
so the 45 committed bars have neither), and **NOT a pin's start** (`standing_pin`
is a bare bool). So A1/A2, A4 and C3 — the families that bound this bank's own
specimens — are uncomputable for committed work from the document, and a census
needs the SNAPSHOT. The blocker analysis is already the one reader that
assembles it. NOT BUILT.

**§5a.63 — A PERSISTED EVIDENCE INDEX WAS NOT A FAITHFUL COPY OF THE INDEX IT
WAS SAVED FROM, AND THE LOSS WAS 25 RECORDS ACROSS FOUR CLASSES, NOT ONE (4B.18
— §5a.55 DISCHARGED, ruling verbatim in docs/04 2026-07-30).** 4B.17 measured
the defect as a single missing M6 `solve_complete` Event. **Item 1's enumeration
over the EMITTERS — not a grep for that string, which would have found 1 of 25 —
showed the cause is in the Reporter and is structural:** `record_event` and
`register_input`/`register_output` hardcode `subjects=[]`, and `record_metric`
defaults to it, so **every Event and every Artifact the system has ever emitted
is subject-less by construction**. `save()` wrote three DERIVED indices and
`load()` rebuilt `_all_evidence` from `entity_records` alone, so every such
record vanished on the round trip. Measured on a real monolithic run, **236 built
-> 211 loaded**: all 12 Events, all 8 Artifacts (**the entire input manifest** —
orders.csv, cost_model.json, the identity map), the **4 M0 conformance rate
Metrics** that `contracts/ids_rules.py` names as what the C0–C3 rules MEASURE,
and one subject-less Finding. On the pinned exam world, 163 -> 148.

**THE FINDING DID NOT MERELY GO MISSING — IT MADE ONE INDEX CONTRADICT ITSELF.**
A subject-less `SOLVER_NONOPTIMAL` was persisted in `finding_index` and absent
from `_all_evidence`, and those back different queries:
`finding_occurrences(...)` returned 1 while `all_findings()` returned 0. Ten
`all_findings()` call sites in `explainer.py` plus `evidence_tools.py:492` read
the side that says zero, and `planner_language.py:75`'s phrase for that code was
unreachable from a loaded index independently of the cost proof.

**FIXED AT THE ROOT RATHER THAN PER-CLASS.** Candidate (ii) — dropping the
load-if-exists preference — was rejected: it leaves an artifact that silently is
not what it was saved from, and the next consumer inherits the hole untold.
Candidate (i) was taken, but NOT as "also persist the run-level records", which
would have been an enumeration and enumerations are what this defect is made of.
**Schema 2 makes `_all_evidence` the PRIMARY persisted structure and DERIVES
`entity_records` / `finding_index` on load through `_index_record`, the same code
path `build` uses** — so they cannot diverge and a record class invented next
year is carried without anyone remembering. It is also smaller (192,767 ->
181,644 bytes, 0.94x): schema 1 stored each record once per subject entity.

**THE INVARIANT, which outlives either fix:** *a persisted evidence index is a
faithful reconstruction of the index it was saved from; any record class the
builder places in `_all_evidence` is recoverable after a round trip, or the load
reports the index as INCOMPLETE and names what is missing.* **Silence is
forbidden: an answer surface may not be unable to distinguish "this never
happened" from "this was not persisted".** `CostProof` gains a fourth state,
`unreadable`, taking priority over the other three so that `no_solve` — a claim
about the PLANT — can never be manufactured out of a fact about our STORAGE.
All three surfaces get an authored branch and **none may stay silent**, including
the money rider, where silence is not neutral because proved is the only other
state that says nothing.

**OLD ARTIFACTS LOAD AND DECLARE THEMSELVES.** A schema-1 file is detected by the
missing `schema_version`; `EvidenceIndex.incomplete` names the CLASSES it cannot
vouch for (classes not counts — a v1 file gives no way to know how many were
dropped, only which shapes could not have survived), and subject-less Findings
are recovered out of `finding_index` so the self-contradiction is repaired even
unmigrated. **FORWARD compatibility is NOT provided and is named rather than
discovered:** a schema-2 file read by pre-4B.18 code yields an EMPTY index —
loud, not subtly wrong, and this repo ships one commit per image.

**THE GUARD ASSERTS BY KIND AND COUNT** (`tests/test_evidence_index_roundtrip.py`
— (record_type, module) census plus the record-id set, never a string search),
its fixture **emits through the real Reporter**, all eight verbs, and it is
parametrized over every real run in `_data/runs/` (14 here). **NEGATIVE CONTROL
PROVEN RED: 19 failed / 7 passed** with the run-level persistence stubbed.
Note the pre-existing `test_load_populates_all_evidence` compared the same two
lengths and passed throughout the defect's life, because its fixture's records
all carry subjects — **a guard that could never have failed.**

**NOT DONE, NAMED:** the seven schema-1 indexes in `_data/runs/` are deliberately
left unmigrated as the live specimens for the incomplete path (a re-solve
migrates any of them free); the Reporter's subject-less verbs are unchanged and
correct — the defect was the persistence assumption, not the records; and **a
schema-2 file that is lossy for some future reason is not self-detecting**
(`incomplete` covers schema 1 only), with the round-trip guard standing in that
gap because a file cannot audit itself and a test can.

**§5a.64 — AN OFFER LABEL NAMES THE QUESTION IT WOULD ANSWER, NEVER THE ANSWER
(4B.19 Items 1-2; ruling verbatim in docs/04 2026-07-30). A1 IS DISCHARGED, AND
THE CLASS HAD FIFTEEN MEMBERS, NOT TWO.** 4B.17 found two by accident; the census
enumerated BY MECHANISM over every authored string that takes an entity slot, and
then had to widen its own population, because **the entity slot is not the
mechanism**: `ROUTE_OFFERS["advice"]` carries no slot and is a member on identical
grounds. Fourteen members in `ROUTE_OFFERS` (of 47) plus one in
`explainer._planner_routes()`, which interpolates a REAL order picked by `min()`
of the external refs into *"why is {order} late"* — on a board where **nothing is
late**. Four surfaces enumerated and CLEARED: `INVITATIONS` (all five rendered
from the answer's own computed facts — they read the board, and that cost is the
reason they are allowed to name a fact), `ROUTE_TAXONOMY.canonical` (restates the
planner's own question), the cockpit's three interpolating templates (composed
from a live board selection), and `planner_language`'s three phrasing dicts.
**GATING EACH DOOR ON A BOARD READ WAS CONSIDERED AND REJECTED:** it is expensive
on the near-miss path and it drifts, and the census found no door needing a gate
for another reason. Guard: `tests/test_offer_labels_do_not_assert.py`, 12 tests,
premise test + negative control proven red out-of-process. **THE GUARD'S REGISTER
HALF IS FRAGILE AND SAYS SO** — a phrase list catches the phrasings we have seen;
the shape half (why-over-a-presupposed-predicate) is general; a third check makes
a NEW slot-bearing table in `ask_fallback_copy` red until it is classified.

**§5a.65 — NO TRUNCATED LIST OF BOARD ENTITIES IS PRESENTED AS COMPLETE (4B.19
Item 3). A2 IS DISCHARGED.** *"The machines here are: "* listed **eight of
fifteen**, alphabetically, silently — dropping **PRESS-FAST, the machine the asked
order is actually on**, and MILL-01/MILL-02, the two a planner typing MILL-99
most plausibly meant. Now: **nearest matches** (`Did you mean MILL-01 or
MILL-02?`), the **total always**, and a pointer at the route that enumerates.
Below a similarity floor **nothing** is proposed — a guess dressed as a correction
is what this route exists to avoid. **PILOT DENSITY IS THE REASON FOR THE SHAPE,
NOT AN AFTERTHOUGHT:** 174 workcenters (§5a) makes any capped enumeration useless
copy, while nearest-first has an output that does not grow with the plant. Census
of six silent truncations: **four were already correct** (the opener's three
lists and the beyond-horizon tray name their remainder AND their total — the
pattern this floor generalizes); two were the defect (machines, orders); three
further silent cuts on adjacent surfaces were closed (edit-summary moves,
prove-it subjects, decision-chain alternatives). Guard:
`tests/test_no_silent_truncation.py`, 10 tests, negative control proven red.

**§5a.66 — THE RIDER, REPORTED AND NOT FIXED: NOBODY READS EITHER OF 4B.18'S TWO
UNVERIFIED CASUALTY CLASSES (4B.19 Item 4).** Measured live on
`_data/runs/7f97d9d1`, an UNMIGRATED schema-1 index. **(a) No answer surface
quotes a conformance RATE.** Asked for one, the synthesis tier answered correctly
that *"no tool exposes that computed percentage directly"* — so the four lost M0
metrics under-report nothing, but **for the wrong reason**: the toolbox has no
metric reader at all, on any schema. Its added clause *"it did not appear as a
gate finding, which is the only place it would be reported"* is false — the rates
are Metric records and they exist in the BUILT index. **(b) Nothing answers "what
was this run built from".** *"which input files was this schedule built from"*
returned the honest unanswerable floor with ZERO tool calls; *"what was this run
built from"* landed on CLARIFY `no-subject` and asked which ORDER was meant. **The
eight Artifact records are declared-but-never-consumed at the evidence level**:
none of the 13 synthesis tools reads them, no route reads them, and the only
`record_type == "artifact"` read in the source is a **dead assignment**
(`dq_report.py:39`, `all_prov_records`, never used). Both feed the next brief.

**§5a.67 — WORKING TIME IS NOT ELAPSED SPAN, AND THE CLASS HAS FOUR MEMBERS
(4B.20 Item 1-3; ruling verbatim in docs/04 2026-07-30). §5a.56 IS DISCHARGED.**
The census was run by MECHANISM, not by name: an AST walk over `src/` for
`.total_seconds()`, timestamp subtraction, `timedelta` construction, sums over
windows, division by a time-ish denominator and unit conversion — then a second
pass binding every hit to what it is ASSIGNED TO, because a subtraction landing
in a datetime is a boundary computation, not a duration. **408 raw arithmetic
sites → 198 bind to a time-quantity name → 63 of those are OFFSETS (an instant
expressed in minutes from the horizon origin — the solver's entire variable
space) → 135 are true durations.** Of the 135: **THREE WRONG, all in
`evidence_tools.py`, all the seam 4B.17 measured**
(`_placement_row.duration_minutes` feeding THREE tools, and
`_machine_occupancy`'s `busy_minutes` in both the row and the summary), and
**ONE LATENT-WRONG** (`board.js`). **"Three and no more" is the result, and it
is only credible enumerated.** Two near-misses are recorded because both are
correct *by mechanism rather than by name*:
`rolling_horizon.compute_manned_idle_metrics` builds occupancy from spans and
then INTERSECTS with the open windows, which recovers working time; and
`explainer._opener_load` reads `run_min` rather than a subtraction, so **the
opener was never affected** — confirmed unchanged by Item 4's regression.
**THE SHARPEST FINDING IS THAT THE TRUER FIGURE WAS ALREADY ON THE ROW:**
`_load_enriched_assignments` has carried `run_min`, `span_min` and `chunks`
since 4B.14, and the toolbox threw them away to recompute the subtraction. 4B.17
recorded "there is no run-time figure anywhere in those rows" — true of the
EMITTED rows, and the source row had it all along. WHY THE JOB CARD GOT IT RIGHT
AND THE DATA SURFACES DID NOT: the card is a RENDERED surface where somebody was
writing prose about the distinction; every seam that got it wrong is a field name
written once by whoever needed a number and never re-read as a claim.

**§5a.68 — THE COCKPIT BOARD WAS RIGHT, AND RIGHT BY A PROPERTY OF THE DATA THAT
NOTHING ENFORCES (4B.20 Item 1).** `board.js` built per-resource occupancy as
`chunks[0].start → chunks[last].end` — the merged span — feeding both the
row-strip utilization % and the open-idle capacity bands. **MEASURED, NOT
ASSUMED: on the pinned world it changed nothing**, because every pause there
falls wholly inside a closure, so intersecting the span with the open windows
(`rowstats.js`) recovers the work exactly — CUT-01 reads 5981 minutes and 89.9%
either way. A pause STRADDLING open time (a `min_chunk` split mid-shift, a
preemption) would have inflated the strip and hidden real idle capacity from the
bands. **4B.13 recorded this seam as "already correct"; it was correct, and it
was not safe.** Now per-chunk, so it is right by construction rather than by
luck. The cross-check that matters: the fixed `machine_occupancy` summary
independently computes **89.9%**, the same figure the board's own strip shows —
two surfaces that agree, neither of which could be checked against the other
before.

**§5a.69 — REPORTED AND NOT FIXED: THE FIXED SURFACE IS NOT REACHED BY THE
QUESTION THAT MOST DIRECTLY ASKS FOR IT (4B.20 Item 4).** *"how busy is CUT-01"*
parses to the contracted `machine-schedule` route at 0.92 — which lists all 18
operations and states **no utilisation figure at all**, so it never touches the
toolbox this session fixed. The utilisation answer is reachable only by a
phrasing that falls to tier two (*"how much of CUT-01's open time is booked"* →
VERIFIED: *"5981 minutes of working time booked against 6655 minutes of open
capacity … 89.9%"*). **A contracted route that answers a "how busy" question with
an enumeration is a vocabulary call**, adjacent to §5a.29's shape: the figure now
exists and nobody can ask a route for it. Separately: *"would splitting the jobs
help"* — 4B.17's A3 specimen — **no longer produces the falsehood, but not
because of this fix**: it now parses to `what-would-change` (4B.16's
counterfactual) and NEAR_MISSES, offering two doors that are unhelpful on a board
where nothing is late. The A3 answer is gone; the route that used to give it is
no longer reached. **Both are honest outcomes and neither is the one the session
was aiming at**, and a future measurement of A3 must ask a phrasing that still
reaches tier two or it will measure the parse instead.

**§5a.70 — A TRUE FIGURE THE VERIFIER CANNOT REBUILD IS CUT, AND THAT IS THE FIX
FAILING QUIETLY (4B.20, ruling clause 4).** Reporting working time made the
figure UNREBUILDABLE from any single evidence record — it is a sum over run
windows, and no record contains it — so the claim verifier's independent
re-fetch failed it. **Measured on the pinned world before this was closed: the
second tier drafted *"puts 1501 minutes of actual work on the machine"* with four
real citations, and verification cut ALL THREE of its claims.** The product had
the right answer and refused to say it. Summary figures were already trusted for
exactly this reason ("our own arithmetic over the pinned run"); derived ROW
figures now are too, through a **named set** (`_DERIVED_ROW_FIGURES`) rather than
"every number in a row" — a value copied verbatim from a record must still be
found in that record, or the re-fetch stops being a check. Pinned by two tests,
one of which goes red if the trusted set is widened. **THE GENERAL LESSON, AND
IT OUTLIVES THIS DEFECT: making an answer truer can make it unverifiable, and a
session that only checks the number would ship the regression.**

**§5a.71 — A COUNT NAMES THE DISPOSITION IT COUNTS (4B.21, ruling clauses 1-2;
the ruling verbatim in docs/04 2026-07-30).** "Orders" alone is not a
disposition. Known, scheduled, committed, active-window, beyond-horizon and
excluded are different sets; a surface reporting one says WHICH, and a predicate
asserted over a count must apply to every member of the set counted. Measured on
the pinned world (40 known / 26 scheduled / 14 beyond / 56 placed of 88 declared
operations), `inventory` said *"40 order(s) are in the plan, scheduled across 56
operation(s) … Every order finishes on time"* — **three denominators in three
adjacent lines and a universal over a set 14 of whose members have no completion
date** — while the opener said "26 orders", the tray said "14 known orders sit
beyond the planning horizon", and the synthesis toolbox's own `lateness_set` note
stated the split correctly. **One board, four surfaces, three answers to "how
many orders", and the surface that was right is the one nobody reads.** Two
clauses ADDED by the census: **(3)** two counts spoken in adjacent sentences
share a denominator or name their own — adjacency asserts a relationship no code
computed; **(4)** where the dispositions do not partition the known set, the
surface says so and states no total, because picking a plausible number converts
a defect in OUR storage into a claim about the plant (4B.18's
`CostProof.unreadable`, in a new place). Fixed by ONE definition —
`order_disposition.census`, every field naming its set — read by six surfaces.
Guard: `tests/test_cross_surface_counts.py`, 10 tests, agreement + prose, its
limit in the module docstring, a premise test asserting a non-trivial split, and
**two negative controls proven red on opposite halves**.

**§5a.72 — CATEGORY FUSION IS THE FIFTH INSTANCE, AND THAT IS A FACT ABOUT HOW
THIS SYSTEM IS BUILT (4B.21).** The delta card fused re-optimisation with the
move (4B.5); `lateness_set` fused not-late with not-scheduled (4B.13);
`CostProof` fused unreadable with no-solve (4B.18); the toolbox fused working
time with elapsed span (4B.20); `inventory` fused known with scheduled (4B.21).
Five unrelated modules, five sessions each believing they were fixing one bug.
**The common mechanism: a NAME is written once, by whoever needed a number, and
never re-read as a claim.** 4B.20 recorded this of DATA surfaces; 4B.21 shows it
is not confined to them — `inventory`'s was a rendered English sentence authored
by a human. **The cheapest place to catch it is the FIELD NAME**
(`known_order_count` cannot be fused); the cheapest place to catch it late is a
cross-surface test, because a fusion is nearly always two surfaces disagreeing on
one board.

**§5a.73 — A5 IS DISCHARGED: THE CHAIN WAS ASSEMBLED FOR THE ORDER AND THE LEAD
COMPUTED FOR THE OPERATION (4B.21).** 4B.13 fixed which decision the LEAD reads
and stopped; the chain kept every assignment Decision of the whole order, merely
REORDERED. So *"why is ORD-000013 op20 on PAINT-01"* led with *"the only machine
qualified to run this step — there was no alternative to weigh"* over a chain
entry for **op10 on CUT-01** pricing CUT-02 at $21.30 and CUT-03 at $49.70, and a
cockpit footer reading *"alternatives weighed: CUT-02, CUT-03"*. **ONE LIST, ONE
SCOPE:** chain, cited refs, lit bars and glowed alternative lanes all derive from
`bundle.ordered_records`, so scoping that one list fixes four surfaces and they
cannot drift apart again. `why-on-machine` now takes an `op_seq` — the taxonomy's
params were (order, machine), so a question naming "op20" had that word dropped
at the dispatch. The order's other steps leave the citation list and are NAMED:
narrowing silently is the same defect as widening silently. **The
driver-phrase-as-whole-clause census found seven sites; the two RENDERER ones are
the class** and now read *"Recorded driver: …"* — a transcription of the record's
own field, which is what it always was. A label is a claim (4B.19); *"Why:"*
claimed to be the reason.

**§5a.74 — A CONTRACT TERM THAT IS ALSO AN ORDINARY WORD WAS DEFINED IN NO
DOCUMENT THE REASONER COULD REACH (4B.21).** Asked *"what's the biggest risk in
this plan"*, the second tier called the 14 beyond-horizon orders *"all inside
this plan's horizon, not beyond it … they were left out of the schedule
itself"* and made normal rolling behaviour the headline risk. **The reasoning was
not careless:** "horizon" was read as the plan's DATE EXTENT (to 9 February),
which is what the word means in English. The contract meaning was **retrievable
from nothing** — docs/01 said nothing about dispositions, docs/05 nothing at all,
docs/06 only inside the `coarse_horizon` coefficient prose, and docs/04 is
HISTORICAL tier, admitted for design-rationale and never for a capability answer.
`"committed"` retrieved **ZERO passages**. docs/01 **§6.10** now states the four
dispositions and, explicitly, the everyday senses that mislead; the fix was FREE
of code change (docs/01 is already CURRENT tier — a section plus
`build_corpus_index.py`). `synthesis_prompt.md` **v4 → v5**, rule 12, makes the
lookup mandatory and adds the standing rule: **when a tool hands you a
disposition word, that word is the answer.** Verified: the tier now reports *"of
the 40 known orders, 26 have a placement … 14 have none … neither late nor on
time"*.

**§5a.75 — REPORTED, NOT FIXED: THE DISPOSITION QUESTIONS ARE CLAIMED BY ROUTES
THAT DO NOT ANSWER THEM (4B.21).** Three phrasings written to reach tier two were
each taken by a contracted route on the pinned world: *"are the fourteen orders
with no placement a problem I should act on"* → `coarse-fit`; *"what does it mean
that work is beyond the horizon"* → `coaching`, which answers *"I don't recognize
which capability you mean"* and lists nine submission fields; and *"why are some
orders missing from the schedule entirely"* → `excluded-orders`. **The third was
FIXED** — it answered *"No data-quality problems — the submission is clean"* on a
board with 14 unplaced orders, true about exclusions and silent about the
disposition asked about, so the clean-submission branch now names the tray. The
other two are vocabulary calls, and they are §5a.69's shape again: **the surface
that holds the answer is not reachable from the question that asks for it.**

**§5a.76 — DEVELOPER OUTPUT ON THE PLANNER'S SURFACE, AND A TAG THAT MEANT ITS
OWN OPPOSITE (4B.21).** Five diagnostic strings could reach an answer; the A5
answer carried *"[LLM validation failed: vacuous causal answer: names no driver,
no entity beyond the question's own subjects, and no quantity; fell back to
template]"* verbatim. The tripwire firing is correct; printing an internal
check's verdict to a planner is not. Detail now goes to the renderer's
`last_diagnostics` and the DEBUG log — routed, not deleted — and the rendered-by
tag `template (LLM validated)`, which read as though the model had validated the
answer, is now `template (model draft rejected)`; the exam sidecar keys its
`validator` tripwire on it and was updated in the same commit, keeping the old
forms so archived sweeps still parse. **RAW SIGNED MINUTES:** `machine-schedule`
printed `-13817min early` — a negative number and the word "early" encoding the
same direction twice, at 1,440 units to the day — while the opener said "8h22m"
off a formatter this listing did not use. One definition now
(`planner_language.elapsed_minutes`); the opener's output is byte-unchanged.
**Six planner-facing sites print raw minutes and three are left**, because R-PD1
clause (4) states the floor and the controllable part in the same unit for
comparability.

**§5a.77 — REPORTED, NOT FIXED: DRILL-DOWN ANAPHORA IS A CONTEXT-LADDER CHANGE
(4B.21).** *"show me the evidence for that"*, asked straight after an answer
carrying a two-record cited chain, answers *"I don't have a claim of my own open
to ground."* The mechanism: `SynthesisMemory` remembers **synthesis answers
only**, so a contracted route's `ordered_records` never enter session memory and
"that" has nothing to resolve to. Fixing it means remembering contracted bundles
per session — the memory contract and the API ask path.

**§5a.78 — THE GUARD WAS GREEN WHILE THE LIVE PATH WAS BROKEN, AND THE LIVE RUN
IS WHAT CAUGHT IT (4B.21).** Every guard test calls `Explainer.route` with a
document in hand. The ASK PATH injects `params["document"]` from an ALLOW-LIST of
intents, and `inventory` was not on it — so the first live verification answered
*"the orders I can account for (0 scheduled, 0 beyond, 0 excluded) do not add up
to the 40 this plan knows about"*, a partition failure the reader invented out of
a missing argument. **Two defects in one:** the documentless fallback read the
enriched rows under a key that does not exist (`order`, not `work_orders`), and
`partitions()` returned a definite FALSE where the honest value is "cannot tell".
It is tri-state now, and `document_read` distinguishes unreadable from empty for
the same reason `CostProof` does. Both halves are pinned, including an assertion
over the interpreter's allow-list itself. **A guard that supplies its own
arguments proves the assembler, not the path.**

## 6. Open rulings queue

1. Requirement model: set-with-roles (docs/05, in progress)
2. Interruptibility: three classes (docs/05)
3. ChangeoverRule: attribute-keyed (docs/05)
4. Min/max lags: OperationSpec vs precedence edge (docs/05; lean = edge)
5. Drop-pin default: machine / start / both — **RESOLVED 2026-07-11 → R-DP1–R-DP7** (both-as-displayed; commit-or-return; semantic snap; gesture=command/language=wish; HOLD/DEFER; legality epistemics; change legibility), extended **2026-07-17 → R-DP8** (an accepted placement is a STANDING commitment, compiled into every subsequent solve of its lineage until an explicit `unpin`). See docs/04 2026-07-11 + 2026-07-17 amendments. **Carry-forward:** the `unpin` release verb (named, not built).
6. The frozen boundary, rush intake, and how a planner expresses intent — **RESOLVED 2026-07-26 → R-F1/R-F2/R-F3** (Session 4B.5 CU6; transcribed verbatim in the docs/04 amendment). **R-F1:** the frozen boundary is PLANNER-MOVABLE; a thaw converts committed work to STANDING PINS, never to free work; every boundary move and thawed edit is evidence; the solver never touches frozen work; re-freezing commits the amended state. **R-F2:** an urgent demand enters as a DEMAND with a deadline due-date and a declared priority weight, never as a hand-placement — the solver places it and the diff shows who paid; boundary thaw is the escalation when it is infeasible against frozen work. **R-F3:** the constraint ladder is OUTCOME -> WINDOW -> PIN, every rung carrying an optional REASON (authored categories + free text, nudged at placement, escalated when the constraint costs money); intent is expressed at its TRUE TIGHTNESS; a constraint rendered infeasible by a changed world fires LOUD, naming its reason. **NAMED-QUEUED, designed not built:** the pin register (docked panel, cost-sorted, unpin ceremony, AI routes); amend-submission (an incremental gate over a delta submission — the phone-call flow, PILOT-RELEVANT); the boundary-drag feature; the window constraint.

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
| WIP invariant amendment regresses the ghost-job fix | ✅ Resolved 2026-07-14: both clamp sites amended together; Validator TEMPORAL_IMPOSSIBILITY exempts in-flight/complete demands while still excluding past-due unstarted ghosts (`test_wip_solver.py` proves both in one run); mid_replan honors an in-flight op with a pre-reference start |
| Session drift | W2: monthly checkpoint + CLAUDE.md same-day |
| CLAUDE.md outgrows its delivery limit (governing rules lost to truncation) | ✅ Addressed 2026-07-25 (CE1): the changelog extracted to docs/04; CLAUDE.md carries position/qualifications/carry-forwards only, checked against a 40k-char ceiling at every phase exit |
