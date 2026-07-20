# Product Roadmap

**Document 7** · Status: v2.30 · Companions: 01–04 (constitution), 05 (Constraint Catalog, in progress), 06 (Incoming Data Spec)

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

**W2 — Documentation & Rulings.** docs/05; the remaining open rulings (queue §6 — drop-pin RESOLVED 2026-07-11 → R-DP1–R-DP7, docs/04 amendment); docs/04 amendments same-commit; CLAUDE.md status current at every session end.

**W3 — Go-to-Market surface (real in Phase 3).** The website, the demo script as repeatable asset, the certificate-as-sales-artifact motion, capability matrix = docs/05 with test-status.

**W4 — Security & Compliance.** Encryption + secrets from first cloud deploy; tenant isolation architectural from tenant #2; audit story half-built by the evidence contract; certification on its trigger, post-window.

## 6. Open rulings queue

1. Requirement model: set-with-roles (docs/05, in progress)
2. Interruptibility: three classes (docs/05)
3. ChangeoverRule: attribute-keyed (docs/05)
4. Min/max lags: OperationSpec vs precedence edge (docs/05; lean = edge)
5. Drop-pin default: machine / start / both — **RESOLVED 2026-07-11 → R-DP1–R-DP7** (both-as-displayed; commit-or-return; semantic snap; gesture=command/language=wish; HOLD/DEFER; legality epistemics; change legibility), extended **2026-07-17 → R-DP8** (an accepted placement is a STANDING commitment, compiled into every subsequent solve of its lineage until an explicit `unpin`). See docs/04 2026-07-11 + 2026-07-17 amendments. **Carry-forward:** the `unpin` release verb (named, not built).

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
