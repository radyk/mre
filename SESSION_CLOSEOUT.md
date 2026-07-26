SESSION 4A.5b CLOSE-OUT
R-AI5 part 2: labeled synthesis, claim-level verification, and the provenance surface
2026-07-26

Deterministic settings for all solver work: PYTHONHASHSEED=0, --solver-workers 1,
--solver-seed 0 (the glass_box pinned world the sweep asks against).

Scope: backend + contracts + a second governed prompt + banks + tests + cockpit
tokens + docs. NO solver / model / schedule-contract / frontend-substrate change.
NO golden moved.

======================================================================
SUMMARY
======================================================================
4A.5a made every question parse first against the closed intent vocabulary and gave
an UNMATCHED intent an honest dead end: the shape recognized, the nearest
capabilities offered, no answer. R-AI5(2) always meant that dead end to be a TIER.

This session builds it. On an unmatched intent -- and only then -- a model reasons
over a CLOSED, read-only evidence tool surface under a stated budget and drafts
STRUCTURED CLAIMS; each claim is then hardened by deterministic code that
independently re-fetches the records it cites and checks what it asserts, yielding
VERIFIED / INTERPRETIVE / FAILED-and-cut; the answer renders as claim blocks with
per-claim provenance visible, in a new `synthesis` register; and "prove it" re-runs
the grounding pass on one claim conversationally.

The ask path is now:

    parse (one LLM call, closed vocabulary)
      -> matched   -> the EXISTING route assembly -> render + validator
      -> unmatched -> the tool surface -> the loop -> claim verification
                                                   -> claim blocks

A matched intent can NEVER reach synthesis; an unmatched one NEVER guesses a route.
Both directions are pinned by dispatch tests.

======================================================================
PART 1 -- PER-CU: CLAIMED vs PROVEN
======================================================================

CU1 -- the read-only tool surface
---------------------------------
CLAIMED: a closed, typed set of evidence-query tools built as thin wrappers over the
         SAME readers the contracted routes use; typed results carrying their record
         ids; the surface enumerated in a governed, versioned module; no tool
         executes an arbitrary query; every call logged to the question ledger with
         its arguments; a per-question tool-call cap and a deterministic overall
         timeout, both stated; exhaustion yields an honest partial, never a stall.
PROVEN:  src/mre/contracts/synthesis.py -- ToolName (11 members),
         TOOL_MEANINGS, TOOL_ARGS, ToolResult, ToolCallLog, DraftClaim, ClaimKind,
         ClaimStatus, Assertion, VerifiedClaim, SynthesisAnswer,
         SynthesisProvenance. Budget stated in the contract: MAX_TOOL_CALLS = 12,
         SYNTHESIS_TIMEOUT_S = 90, MAX_ROWS = 60.
         src/mre/modules/evidence_tools.py -- EvidenceToolbox over one Explainer:
         placements_for_order / _for_machine / _in_window, machine_occupancy (spans,
         gaps between them, busy totals), lateness_set (the WHOLE set), cost_ledger
         (totals row + per-order tardiness lines), gate_findings, calendars,
         capability_registry, entity_vocabulary, fetch_record. Rows carry
         `record_ids`; a placement row cites every source that carries a value it
         reports (assignment Decision + assignment entity + demand + resource), so a
         claim quoting the machine name or the due date can ground.
         src/mre/modules/synthesis_prompt.md -- the governed artifact: header names
         R-AI5(2)/(3)/(8), carries prompt_version, and states the review discipline
         (a change is a vocabulary-class change, reviewed, committed with the doc
         update). The tool list is RENDERED from the contract, never re-authored.
         Budget enforcement + logging: EvidenceToolbox.call is the ONLY model-facing
         entry; an unknown tool, a missing required argument, a reader failure and an
         over-budget call are all honest ok=False results, all logged. The ledger
         entry carries every call with its args (QuestionLedgerEntry.synthesis).
         fetch_source (the verifier's re-fetch) is deliberately NOT budgeted and NOT
         model-callable.
         tests/test_synthesis.py::TestToolSurface -- vocabulary parity, the governed
         artifact's header + placeholders, the rendered surface naming every tool,
         EVERY tool live-implemented, rows carrying re-fetchable ids, the budget cap,
         per-call argument logging, and a read-only vocabulary guard (no tool name
         may contain a mutation verb).

CU2 -- the synthesis loop
-------------------------
CLAIMED: on an unmatched intent AND ONLY THEN (a dispatch test pins it), the model
         gets the question, the conversation context and the CU1 surface; reasons in
         an agentic loop under the budget; produces a draft as structured claims,
         each a sentence plus the record ids it believes support it; the draft never
         renders directly.
PROVEN:  src/mre/modules/synthesizer.py -- one strict-JSON object per turn: a tool
         call, a claims list, or an honest cannot_answer. A malformed emission is
         nudged once. At budget/timeout the loop is TOLD and asked for what it has
         (an honest partial naming what it consulted). synthesize() = draft, then
         verify; only the hardened SynthesisAnswer leaves the module.
         tests/test_synthesis.py::TestSynthesisLoop -- the loop calls tools then
         answers; a malformed emission survives one nudge; budget exhaustion yields a
         partial, never a stall; cannot_answer is the honest floor; an unavailable
         synthesizer returns None. THE SEAL: a matched intent dispatched with an
         EXPLODING synthesizer still routes (it can never reach the tier); an
         unmatched intent reaches synthesis and never a route; a low-confidence parse
         goes to synthesis rather than being answered AS the intent; with no
         synthesizer the floor is part 1's bridge.

CU3 -- claim-level verification
-------------------------------
CLAIMED: deterministic code, not a model; independently fetches the cited records and
         checks the claim's specific assertions against them with the render
         validator's discipline; VERIFIED / INTERPRETIVE / FAILED; a FAILED claim is
         cut and, if load-bearing, said out loud; a wholly-failed draft is the honest
         couldn't-answer; completeness honesty on quantifiers; tests covering every
         outcome, the fabricated-id draft, and the correct-but-uncited claim.
PROVEN:  src/mre/modules/claim_verifier.py -- verify_claim / verify_draft. Fetches
         through EvidenceToolbox.fetch_source (evidence index + snapshot), never the
         loop's transcript. Checks: timestamps as minute tuples (renderers'
         _to_minute_tuple / _ts_matches), durations normalized across
         minutes/hours/days with comparatives read as inequalities, entity names
         resolved through the identity map, figures against the toolbox's own
         tallies, citations required to name a real record.
         Outcomes: VERIFIED requires every checkable assertion to ground, at least
         one of them a FIGURE or a TIME rather than a name, the claim not to be the
         draft's own conclusion, and any quantifier to have been enumerable from a
         single tool call. FAILED = a contradiction, a fabricated citation, or an
         entity this run does not have. Everything else is INTERPRETIVE.
         load_bearing is computed over the whole draft (conclusion, or nothing
         verified survives) -- never asserted by the model.
         tests/test_synthesis.py::TestClaimVerification -- one hand-built draft per
         outcome: verified; verified through an honest unit conversion; a wrong
         figure against a cited record CUT; a fabricated citation ("finding 2") CUT;
         an entity this run does not have CUT; a wrong timestamp CUT; correct-but-
         uncited -> INTERPRETIVE (never promoted); a reading with nothing checkable
         -> INTERPRETIVE; a name alone does not prove a sentence; a conclusion is
         never promoted; a quantifier verified only when the set was enumerated, and
         over a sample -> INTERPRETIVE with the sample named; an under-cited figure
         INTERPRETIVE while a figure nothing read carries is still CUT; a cut
         conclusion is load-bearing; a wholly-failed draft is unanswerable; the
         counts report every outcome.

CU4 -- the answer surface
-------------------------
CLAIMED: claim blocks with per-claim provenance visible; verified claims cited like
         testimony, interpretive claims with a distinct `synthesis` register tag and
         a visible marker (treatment shipped as tokens); the rendered-by line names
         the tier and the tool-call count; mixed answers expected; "prove it" as a
         parse follow-up kind that re-runs the grounding pass conversationally;
         corpus specimens.
PROVEN:  src/mre/modules/renderers.py -- _render_synthesis (claim blocks:
         "[record: ...]" on verified, "[synthesis -- read from: ...]" on
         interpretive, the sample note where a quantifier rests on a sample, the
         load-bearing-cut note, the budget note) and _render_prove_it; _rendered_by
         names the tier + tool-call count; "synthesis" and "prove_it" join
         _HEADER_ONLY_SUBJECTS and _AUTHORED_COPY_SUBJECTS (a verified claim's WORDS
         are what the label is attached to, so the rendering model never rewords
         them -- pinned by a test whose LLM client raises if reached).
         src/mre/modules/explainer.py -- REGISTER_BY_SUBJECT gains synthesis (chip
         and envelope still resolve through one source); _synthesis_bundle /
         _prove_it_bundle / _records_by_id / _record_summary.
         src/mre/modules/ask_fallback_copy.py -- every framing string authored (the
         markers, the lead, the ungrounded note, the partial note, the honest
         couldn't-answer, the prove-it copy).
         Cockpit: --reg-synthesis / --reg-synthesis-fill / --synthesis-mark-ink /
         --synthesis-mark-bg in BOTH themes, the .synthesis register card + chip in
         cockpit.css, askpanel.js's register whitelist, voice.js speaking the tier.
         Prove it: FollowupKind.PROVE_IT (contracts/parse.py), parse_prompt.md v2,
         dispatched BEFORE intent (what is questioned is our sentence, not the plan),
         SynthesisMemory carrying our own last answer per session, pick_claim
         selecting deterministically among sentences we already said.
         tests/test_synthesis.py::TestAnswerSurface -- claim blocks carry per-claim
         provenance; register == synthesis; rendered-by names tier + count; the LLM
         renderer never rewords a verified claim; a failed load-bearing claim is said
         out loud AND the cut claim's figure never appears (not even in the apology);
         a wholly-failed draft says it could not answer and names what it consulted;
         the ledger records per-claim provenance and every call with its arguments;
         prove-it on a verified claim shows the record, on an interpretive claim
         names it as inference and lists what it was read from, with nothing to prove
         says so, and precedes intent. NAMED SPECIMENS: the aggregate-cause answer
         (verified per-order facts + a labeled interpretive conclusion, neither
         wearing the other's clothes) and the occupancy read (fully verified).

CU5 -- the acceptance sweep + riders
------------------------------------
CU5 -- the acceptance sweep + riders
------------------------------------
CLAIMED: (a) the ENTIRE bank set plus a new synthesis bank (>= 15 uncontracted
         questions plus prove-it follow-ups) fired LIVE against the pinned world
         into sweeps/<date>-synthesis/; the sidecar gains synthesis-claims total /
         verified / interpretive / failed-and-cut, the ungrounded-load-bearing
         count and a tool-call histogram; bar: every mechanical baseline signal
         strictly-no-worse, the two 4A.5a expect-misses resolved, zero FAILED
         claims rendered.
         (b) the capability registry gains the min_chunk / "minimum piece size"
         trigger, authored and section-cited.
         (c) TOTAL conversational latency stated: parse+route vs parse+synthesis,
         median and p90.
         (d) a ruling on the rolling pre-route's fate.
PROVEN:  (a) tests/ai_exam/sweeps/2026-07-26-synthesis/ -- SIX banks, 304
         questions, live, one shared parser and ONE shared synthesizer so both
         tiers' counts are the sweep's. New bank banks/sweep_synthesis.txt, 30
         questions, uncontracted by construction, including a
         SEAL-FROM-THE-OTHER-SIDE section of contracted questions that must NOT
         reach the second tier.
         RESULT: 90/93 graded expectations met (baseline 61/63 over 274).
         Mechanical signals: exception 0, empty 0, validator 0, dark-evidence 0,
         dead-door 0 -- all as baseline -- and absent-entity 3, IDENTICAL to the
         baseline's three. On the SHARED banks expect-miss went 2 -> 1. Zero
         FAILED claims rendered. Parse: 317 parses, 0 retries, 0 malformed
         (baseline 2 and 4), 6 clarifies, median 1050ms.
         THE TIER: 32 synthesis answers, 100 claims -- 42 VERIFIED, 55
         INTERPRETIVE, 3 FAILED-and-cut (3 load-bearing, each said out loud), 8
         honest couldn't-answers, 96 tool calls, 0 budget exhaustions, 0 timeouts.
         THE SEAL, MEASURED: 6 route moves across 212 shared questions; the
         120-question route fan moved NOTHING.
         BOTH 4A.5a expect-misses resolved: "whats holding CUT-01" now reaches
         synthesis with a real occupancy read lighting 7 bars; "is there a minimum
         piece size" binds concept=min_chunk.
         (b) capabilities.py -- a min_chunk CapabilityNote, section 5.3, ordered
         FIRST so it wins over the bare chunk/split triggers; live in the sweep.
         (c) route n=272 median 1275ms p90 2502ms; synthesis n=32 median 9659ms
         p90 16030ms (the loop's own median is 8235ms of that).
         (d) RULED 4A.5c SCOPE, with the reason: the parse resolves SUBJECTS
         against the Explainer's snapshot, which on a rolling run is window 0
         only, so an order in the beyond-horizon tray would resolve to nothing and
         be answered as ABSENT -- a confident-wrong answer replacing a correct one.
         Retiring the pre-route needs the rolling document's vocabulary in subject
         resolution first (the connector-era debt named in rolling_questions.py).

         THE SWEEP RAN FIVE TIMES. Each run found a defect in the SHIPPED path
         that offline tests could not, and a committed sweep that does not match
         committed code is not evidence:
           1 the parse stretched aggregates into contracted routes -> prompt v3
             (unmatched is ANSWERED, not refused)
           2 a machine typed as an order was answered "not in this schedule"; a
             clarify that could not have helped -> two dispatch repairs
           3 {"intent": "prove-it"} discarded as malformed -> prove-it becomes an
             Intent as well as a follow-up kind (v4). Diagnosed ONLY because the
             sweep had just gained malformed-emission sampling, added when run 1
             produced a parse-failed nobody could explain.
           4 {"intent": "list-expand"} -- the same misfiling class -> coercion
             instead of discard (v5); and prove-it grounding a STALE claim after a
             contracted answer -> the memory clears on any other answer
           5 prove-it then over-attracted "but why" on the founder's own r4 bank
             and dead-ended -> v6 separates deepen from prove-it, plus a dispatch
             floor that answers a named intent when nothing is open to ground
         Run 5 is the committed artifact. Runs 3 and 4 overlapped in the same
         directory because run 4 was launched before run 3 had exited; that mixed
         artifact was DISCARDED, and run 5's integrity was verified by file
         ordering (every file monotonic inside the run's own window), not by the
         shared log line that caused the mistake.

CU6 -- docs
-----------
CLAIMED: docs/04 (the tool surface as a governed artifact, the verification outcome
         taxonomy, the prove-it linkage, rider d's ruling); docs/07 same-day;
         CLAUDE.md (the ask-path paragraph gains the second tier); RUBRIC.md
         (synthesis grading guidance).
PROVEN:  docs/04 -- "2026-07-26 -- AI-track Session 4A.5b" appended under the
         Amendment log (pure append; the pre-append bytes are a verbatim prefix of
         the post-append file).
         docs/07 -- v2.45 entry inserted above v2.44, status line bumped.
         CLAUDE.md -- position updated; the ask-path paragraph rewritten as TWO
         TIERS with the seal in both directions and R-AI5(8) named as the hard rule;
         rider (d)'s ruling and the verification pass's named limits added to the
         carry-forwards. 13,166 chars, well under the 40k ceiling.
         RUBRIC.md -- a new "GRADING A SYNTHESIS ANSWER" section (verified claims
         graded as testimony; interpretive claims graded on groundedness-of-reasoning
         and usefulness per R-AI3, never on being provably optimal; the cut count is
         not a grade; what the label must never be), the two new sidecar signals, and
         the second tier's counts named as instrumentation.
         pyproject.toml -- the package-data comment now covers both governed prompts.

======================================================================
PART 2 -- VERIFICATION
======================================================================
Full non-slow Python suite     1386 passed, 199 skipped (10:17)
Slow AI-track suites            163 passed -- test_ai_voice, tests/ai_exam,
                                test_ask_chain_api with --runslow
Cockpit JS (Playwright)         178 passed (2.4m), light + dark
New tests                       tests/test_synthesis.py -- 57, covering the tool
                                surface, the outcome taxonomy one hand-built
                                draft at a time, the seal in both directions, the
                                answer surface and prove-it
Sweep                           committed under
                                tests/ai_exam/sweeps/2026-07-26-synthesis/
Goldens                         none moved -- no golden file appears in the diff
Payload                         the cockpit ask payload is unchanged; the ask
                                RESPONSE gains a read-only `synthesis` metadata
                                block (counts + tool names), consumed only by the
                                exam sidecar

======================================================================
PART 3 -- UNDERDELIVERED, RESIDUE, OUT OF SCOPE
======================================================================
UNDERDELIVERED (explicitly):
  - Three graded expectations remain unmet and were NOT relaxed to match
    behaviour. "are you sure about that" reaches prove-it rather than the
    verification clarify (both honest; logged as a founder precedent question).
    "how much of CUT-01s week is actually working time" -> downtime, which answers
    the complement of the question. "how many orders will be late next month" ->
    late-orders, which answers about THIS plan a question asked about next month.
  - Two of my own bank expectations WERE corrected, and the reason is stated:
    "can jobs run across a night shutdown" expected a concept the sibling bank
    does not expect on the opener, and "what would happen if CUT-01 went down"
    excluded `advice`, whose AUTHORED meaning explicitly covers hypotheses about
    changing the plant. Both were authoring errors in a bank written this session,
    not behaviour bent to fit.
  - The per-claim cockpit BADGE is not built: the register card, the chip and the
    --synthesis-mark-* tokens ship, and the panel still renders the answer body as
    one <pre>, so the per-claim treatment lands when the claim blocks become their
    own elements. The brief scoped this to "shipping the tokens".

NAMED RESIDUE (carried, also recorded in docs/04 and CLAUDE.md):
  - The ROLLING pre-route is 4A.5c scope, with its reason (rider d above).
  - Verification limits, stated rather than implied away: a COUNT is checked
    against the enumerating call's own tallies, not typed to the predicate beside
    it; a percentage or ratio the model computes can never be verified and lands
    interpretive by construction; a real entity the cited records do not mention
    is UNDER-CITED (interpretive), not contradicted; a fabricated figure that
    coincides with something else the loop read is labeled, not cut.
  - The synthesis floor on a frustration turn ("this is not helpful") is the
    honest couldn't-answer, where part 1 gave the near-miss bridge with two
    offers. Colder, and offering no door. Logged as a founder precedent question.
  - start-reason's early-vs-plain read is still the assembler's own; a CLARIFY
    turn still carries no subject forward.
  - Synthesis costs about 7.5x a contracted answer's median latency. Nothing paces
    or streams it yet; the planner learns which tier answered only when it lands.

OUT OF SCOPE (named, not built):
  - Provenance telemetry aggregation, the frequency-weighted Pareto and the
    promotion loop (R-AI5(5)/(7)) -- 4A.5c.
  - Any promotion of a synthesis shape into a contracted route.
  - New contracted route content beyond rider (b).
  - Rendering-model changes; cockpit visual tuning beyond the tokens.
