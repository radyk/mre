# Micro-session 4A — the shared-body census + the certificate route

**2026-08-04.** R1 docket item, routed from (d.0)/(d.1) (docs/07 §5b). One
census, one fix, one guard. The extras the census found are ledgered with owners
and are **not** fixed here.

---

## 1. Why this was a species question, not a one-route bug

`deaf` caught the same specimen twice across two sessions — (d.0) P6 T7 and
(d.1) sweep block E2: *"what does the certificate say"* and *"are there any data
quality problems"* rendered **the same body**. Two intents with different
declared meanings, one answer.

One shared body found twice by accident implies nothing about how many exist, so
the census came before the fix. The predicate, stated once and applied
uniformly:

> Two intents with **different declared meanings** (the `contracts/parse.py`
> docstrings are the authority) whose rendered bodies are identical, or differ
> only in framing lines, are one defect — a planner reading the body cannot tell
> which question was answered.

Byte-identity is sufficient but not necessary. The (d.1) drill-down/prove-it
unification is explicitly **not** a finding: those two gestures were *ruled* one
gesture, so their bodies agreeing is the fix working.

---

## 2. C1 — the code-level census

Mechanical, not by eye: `_route_inner`'s dispatch chain parsed with the AST, so
a route added since cannot hide from the map
(`scratchpad/census_c1.py`, reproduced in §9).

**41 routes in the dispatch chain. 3 assemblers are reached by more than one
route. 17 sharing pairs.**

| assembler | routes | pairs | given a discriminator? |
|---|---|---|---|
| `_explain_data_problems` | `certificate-testimony`, `data-problems` | 1 | **NO** |
| `_rolling_bundle` | `beyond-horizon`, `why-not-scheduled-yet`, `frozen`, `coarse-fit`, `bucket-load` | 10 | yes — takes `route_id`, branches five ways |
| `_schedule_query` | `schedule`, `machine-schedule`, `order-schedule`, `customer-schedule` | 6 | yes — branches on a subject-derived filter |

**THE CENSUS'S REAL FINDING IS THE LAST COLUMN.** Sharing plumbing is fine and
expected. What separates the defect from the other two is that
`_explain_data_problems` was handed **only `entity_ref`, never the route id** —
so it was *structurally incapable* of knowing which of two questions it was
answering. It could not have done otherwise. The other two receive the
discriminator and branch on it.

That is why the guard for this is a property test
(`test_no_two_differently_meaning_intents_share_an_undiscriminated_assembler`)
and not a string assertion about one route.

---

## 3. C2 — the live census

Both members of the certificate pair are **authored copy**
(`subject_type` in `_AUTHORED_COPY_SUBJECTS`), so their bodies are deterministic
and need no LLM — which is exactly what makes byte-comparison the right
instrument. Driven on the pinned `glass_box` run
(`_ai_exam_scratch/gb_pinned`, read-only).

| pair | shared source | verdict | specimen |
|---|---|---|---|
| `certificate-testimony` / `data-problems` | `_explain_data_problems` | **SHARED BODY → FIXED** | sha256 `39022447757c0386` **both**, before |
| the 10 `_rolling_bundle` pairs | `_rolling_bundle` | **DISTINCT** (0 of 10 identical) | each states its own thing even in the degraded monolithic case |
| `schedule` / `customer-schedule` | `_schedule_query` | **SHARED BY DESIGN, degenerate probe only** — ledger row S-01 | see below |
| the other 5 `_schedule_query` pairs | `_schedule_query` | **DISTINCT** | — |

**Exact count: of 17 sharing pairs, ONE was a shared body.** The rolling group is
the good case worth recording — even its five *"this isn't a rolling schedule"*
refusals are individually worded, so a planner is told which question was
declined.

`schedule` / `customer-schedule` collapsed **only** under a synthetic probe
naming no customer at all. Re-probed fairly, `customer-schedule` discriminates:
a named-but-unknown customer gets *"I don't see any scheduled operations
matching that"* / *"Nothing scheduled for customer acme."* The parse selects that
route *because* a customer is named, so the collapse is not reachable from a real
question. Recorded as a ledger row with the caveat, **not** claimed as a defect.

---

## 4. The fix — the certificate route states the certificate

### 4.1 What the certificate actually is

Read from docs/02 and the gate itself, not assumed. `ConformanceGate` builds a
certificate dict carrying `grade` (REJECTED / CONDITIONAL / ACCEPTED),
`costing_completeness_grade` (C0–C3), `rule_outcomes` (29 rules on this
submission), `deficiencies`, `normalizations`, `flags_disclosed`, `findings`,
`counts`, `generated_at`, `run_id`, `submission_dir`.

### 4.2 The persistence fact that decided the design — and the §3 STOP that did NOT bind

**The grade is never emitted to the Reporter.** It is computed by
`grade_from_outcomes` and written to the `certificate` dict, which `__main__`
writes to `out_dir/certificate.json`. And `record()` — the gate's finding
emitter — **returns `None` and emits nothing when a rule is SATISFIED**. So on an
ACCEPTED submission with no deficiencies the evidence store is **completely
silent about the certificate**. `_opener_certificate`'s own docstring says as
much and returns `{"grade": None}`.

The brief's §3 said: stop if the field is *"computed but not persisted where the
route can read it"*. **It is persisted where the route can read it.** The
Explainer already holds `self._out_dir`, and reading the run directory is
precedented — `local_price` does it for the ledger, which is the reason that
attribute exists at all (4B.30 Item 3). So the route reads the artifact the gate
wrote. That is *read from evidence, never re-run the gate* — the same handoff
rule `_certificate_findings` already keeps — not an exception to it.

Recomputing the grade here was refused: `grade_from_outcomes` is pure, so calling
it would have been cheap and would have created a **second definition of the
verdict**.

### 4.3 Four states, never two

`_read_certificate` returns `no_run_dir` / `absent` / `unreadable` / `present`.
This is 4B.18's `unreadable` species again, with its priority rule: a corrupt
certificate is not an absent one, and a claim about the SUBMISSION is never
manufactured from a fact about our STORAGE. Each degraded state gets its own
sentence and **none falls through to the findings list** — which is exactly what
the defect was doing. A missing `grade` inside a *present* certificate is
likewise reported as its own fact rather than defaulted to a word (4B.23's rule,
at a fourth site).

### 4.4 What was deliberately NOT changed

`ordered_records` stays `_report_findings()` — the **same set** testimony,
remediation and triage reason over. Narrowing this route to gate-only findings
would have put the registers back into the contradiction 4A.2b CU2 ended (an
ACCEPTED submission carrying a validator advisory saying "1 problem" here and
"nothing" there). **What changed is what the answer LEADS with, and that the
grade is stated at all — never which findings are in evidence.**

### 4.5 Before and after, verbatim, same board, same instrument

**BEFORE** — both routes, sha256 `39022447757c0386`, `IDENTICAL BODIES: True`:

```
1 data-quality problem(s):

  1. the customer priority weight is only weakly known for 13 order(s), so tardiness priority is unreliable  [WARNING]
       Affected: ORD-01, ORD-02, ORD-03 — 13 in all
       Fix: Declare each order's customer priority (its weight) in the submission so tardiness ranking isn't defaulted.
[rendered by: template | register: testimony]
```

**AFTER** — `certificate-testimony`, sha256 `c48508b74fc723ae`;
`data-problems` unchanged at `39022447757c0386`; `IDENTICAL BODIES: False`:

```
Intake review: ACCEPTED — costing completeness C2.
29 gate check(s) ran against this submission: 29 satisfied.
No deficiencies, nothing normalized, nothing flagged.
This is the gate's own record, generated 2026-07-26, and it is unsigned — nobody has countersigned it.

Behind that, the problems on the record:

1 data-quality problem(s):

  1. the customer priority weight is only weakly known for 13 order(s), so tardiness priority is unreliable  [WARNING]
       Affected: ORD-01, ORD-02, ORD-03 — 13 in all
       Fix: Declare each order's customer priority (its weight) in the submission so tardiness ranking isn't defaulted.
[rendered by: template | register: testimony]
```

**THE ANSWER NOW SHOWS THE 4A.2b SPECIMEN IN ONE SCREEN:** the gate passed all 29
of its checks and issued ACCEPTED with no deficiencies, *while* a validator
advisory stands. Both true, from different layers — and a planner can now see
which is which, instead of reading the advisory as the grade. That is asserted in
`test_an_accepted_grade_coexists_with_a_standing_advisory`.

### 4.6 On the signature

The certificate artifact has **no signature field at all**. The answer therefore
states it is unsigned, which is true of the artifact. R-CAL1's
measured-never-authored signature belongs to `CalibrationProfile`, a different
artifact; inventing a signature concept for the certificate would have been the
manufacture the rules forbid. Ledger row **S-03**.

---

## 5. The guards

`tests/test_certificate_route.py` — **15 tests**, all green.

- the two bodies differ; the certificate body **quotes** the grade, the costing
  grade and the coverage count off the artifact (never recomputed on either
  side);
- `data-problems` is unchanged and must not start claiming the gate's verdict;
- the findings detail is the **same record set** in both (4A.2b coherence,
  asserted by `record_id`);
- all four artifact states, plus present-with-no-grade, zero-findings, and a
  REJECTED lead. **No pinned board was mutated** — the degraded states are reached
  by pointing `out_dir` at a `tmp_path`;
- the census **property**, per §2;
- `test_deaf_is_silent_on_the_pair`, with the explanatory comment the brief
  required (§5.1).

### 5.1 The deaf silence, and the trap in the old bank comment

The rider's one true positive is now **extinct by repair**, and the assertion of
silence carries a comment saying why silence is correct: the gate is untouched;
it is quiet because the condition it detects no longer holds. The fixture
supplies `followup_of=DEEPEN` — **the value the live parse actually reports on
that turn**, measured in (d.1) — rather than a convenient one, so the silence
proves the BODIES and not the gate. If the test goes red the two bodies have
collapsed back together, which is the defect, not the rider.

**The carried-state bank said the opposite and had to be corrected.** Its E-block
comment read *"If E2 ever stops firing, the gate has become a suppression."* That
was true when written and is now false; left alone it would have led a future
session to "restore" a firing whose defect had been fixed. Corrected in place,
with the correction and its reason stated in the comment.

### 5.2 Negative controls — 3, all RED, all restored byte-identical

Bytes only, never `write_text` (this repo mixes line endings per file; both
touched files are pure CRLF).

| control | reverts | verdict | restore |
|---|---|---|---|
| NC1 | the dispatch back to `_explain_data_problems` (the defect verbatim) | **RED** — 5 failed | sha256 identical |
| NC2 | the `unreadable` branch demoted, so a corrupt certificate reads as never-gated | **RED** — 1 failed | sha256 identical |
| NC3 | the grade sentence dropped, degraded states falling through to findings | **RED** — 3 failed | sha256 identical |

Each control asserts its anchor was **found** before replacing (4A-(a)'s lesson:
an anchor that matches nothing reports ANCHOR NOT FOUND rather than passing
falsely).

---

## 6. Suites

**THE UNCHUNKED DATUM WAS OBTAINED, AND IT CONTRADICTS MY OWN FIRST READING.**
(d.1) reported the environment killing three consecutive full runs; the brief
asked for the unchunked datum if it could be got. It could:

| run | result | wall |
|---|---|---|
| **full suite, UNCHUNKED** | **2682 passed / 309 skipped / 0 failed** | 22m15s |
| chunk 00 (re-run, post index rebuild) | 675 / 184 / 0 | 2m49s |
| chunk 01 | 839 / 38 / 0 | 8m09s |
| targeted (`certificate|findings|renderer|explainer|rider|…`) | 283 / 16 / 0 | 1m17s |
| `tests/test_certificate_route.py` | **15 / 0 / 0** | 1.5s |

**I called that run killed and I was wrong** — its output file was empty only
because pytest buffers under `-q` and the run outlived my wait loop. It completed
cleanly at exit code 0. Recorded because the "full runs get killed here" belief
is now one session for and one against, and the next session should test it
rather than inherit it.

**THE DELTA IS EXACTLY +15 AND IS MEASURED, NOT INFERRED:**

```
collection, this tree, with the new guard file   : 2991
collection, same tree, --ignore that ONE file    : 2976
                                                   ---- +15, the new file's own count
```

So **baseline 2667 / 309 / 0 → after 2682 / 309 / 0**. The baseline figure is a
subtraction rather than a second 22-minute run, and that is stated rather than
dressed up: it is sound because the full run had **zero failures** and no
existing test changed collection status.

**NOT COMPARABLE TO (d.1)'s 2700/305/0, AND THE REASON IS KNOWN.** `_data` is
**empty in this tree** (the pinned boards are gitignored artifacts and are not
present), which (d.1) itself recorded as worth ~29 tests of collection. Its 3005
against this tree's 2991 is that gap, not a regression. I did not re-mint a board
to close it — the brief forbids re-minting the pinned worlds, and nothing in this
session needs one.

**ONE RED, PREDICTED, CAUSED BY THIS SESSION, AND FIXED:**
`test_corpus.py::TestCurrency::test_index_matches_the_live_docs` went red in the
first chunk-00 run because I had amended `docs/04` without rebuilding the corpus
index — the 4B.33 / (c2) shape, third occurrence. `python tools/build_corpus_index.py`,
then 22/22. Chunk 00 was re-run afterwards and is the run of record for that
slice. The unchunked run predates the amendment and is internally consistent
(its `test_corpus` ran against the un-amended docs).

**KNOWN REDS NOT OURS, UNTOUCHED AND NOT RE-RUN:** `--runslow`'s
`test_ai_voice.py::test_cu5_split_jobs`; the cockpit deictic pair. **THE COCKPIT
IS UNTOUCHED AND WAS NOT RE-RUN** — no `src/cockpit/` file was opened.

## 6a. The sweep

`sweep_shared_body_v1` against `_ai_exam_scratch/gb_pinned` (snap-exam), live
parse **v18**, live synthesizer **v8**:

```
questions 5 · llm calls 5 · parses 5 · retries 0 · malformed 0 · clarifies 0
graded : 5/5 expectations met
sidecar: clean
```

The certificate turn parses `intent=certificate-testimony conf=0.92
followup=deepen` — **`deepen` is the same value (d.1) measured**, which is why
the (d.1) deaf gate has to read the prior delivery's ROUTE and not `followup_of`
alone. Live through the real ask path, the body is the §4.5 "after" verbatim.

**And this is the Q7 line made concrete: all 5 of those expectations would have
been MET on the broken product.**

---

## 7. What a summary would undersell

1. **The census's value was the discriminator column, not the count.** "One
   shared body of 17 pairs" reads like a near-clean bill of health. The finding
   that matters is *why* this one was shared: it was the only assembler never
   told which route called it. That is a mechanical property a future session can
   re-check, and it is what the property guard pins — a count cannot be guarded.

2. **The route was routing correctly the entire time.** Two questions, two
   intents, two routes — the parse was never wrong. Every EXPECT line in the exam
   bank passed on the broken product and would still pass today. The defect lived
   strictly below the layer the exam grammar can see. That is the sharpest Q7
   input this repo has produced (§8).

3. **The evidence store cannot answer the certificate question and nothing said
   so.** `record()` emitting nothing on SATISFIED means an ACCEPTED submission
   leaves the gate *silent* in evidence. Anything reading evidence alone — the
   opener, correctly, returns `grade: None` — cannot state the grade. The route
   works around it by reading the artifact; the underlying contract gap is
   ledgered (S-02), not papered over.

4. **The fix made a real coherence case visible rather than creating one.**
   ACCEPTED-with-a-standing-advisory was always the truth on this board; before,
   the planner saw only the advisory and had to infer the grade from it.

---

## 8. The Q7 input line

> **The exam grammar cannot express "these two answers must not be the same
> answer."** `EXPECT` grades eight keys, all properties of one turn's PARSE. The
> shared-body defect was invisible to every one of them: the routing was correct
> throughout, so a 100% sweep of `sweep_shared_body_v1` is fully consistent with
> the defect being fully present. In a repo whose ask layer is mostly *authored
> bodies*, the sharpest regressions live exactly where the format is blind — so
> whatever Q7 decides must either add a body-level assertion or state plainly
> that bodies are guard-file territory and banks grade routing only.

What the sweep grades here: **routing** (and it is worth grading — the fix must
not be paid for by collapsing two intents into one, which this bank would catch).
What only the unit tests grade: **every body claim** in §4.5 and §5.

---

## 9. Ledger — extras found, NOT fixed, with owners

| id | finding | severity | owner |
|---|---|---|---|
| **S-01** | `schedule` and `customer-schedule` render one body when the route is reached with no customer in the text. Not reachable from a real question (the parse selects the route *because* a customer is named, and a named-but-unknown one is disclosed). Recorded for completeness with its caveat. | cosmetic / unreachable | R1 |
| **S-02** | **The gate's grade is in no evidence record.** `grade` / `costing_completeness_grade` / `rule_outcomes` are written to `certificate.json` only; `record()` emits nothing on a SATISFIED rule, so an ACCEPTED submission is silent in the evidence store. Any surface reading evidence alone cannot state the grade — `_opener_certificate` returns `grade: None` and says so. A Metric or Artifact record at the gate is the fix shape; it is a contract change and **not** a micro-session's. | contract/persistence gap | R1 |
| **S-03** | The certificate carries **no signature field**. The answer states it is unsigned, which is true; whether a certificate *should* be countersigned (R-CAL1's discipline for `CalibrationProfile`) is a vocabulary/contract question. | unruled | R1 |
| **S-04** | The census covers the CONTRACTED routes reached through `_route_inner`. Synthesis, prove-it and the rolling answerers' own internal copy were not swept for shared prose. Stated as a bound on the census, not a claim of cleanliness. | census bound | R1 |

**Out of scope and untouched, as briefed:** every S-row above; intent vocabulary
changes; prompt bumps (parse **v18**, synthesis **v8**, both UNCHANGED — this was
a route body, not a prompt); docs/06 doorways; the (d.2) ladder work; teaching
persistence.

---

## 10. What was minted

**NOTHING WAS MINTED IN `_data`** — it is empty in this tree and stayed empty. No
board was solved, no run directory created, no schedule registered.

**NEITHER PINNED BOARD WAS RE-MINTED OR MUTATED.** `_ai_exam_scratch/gb_pinned`
was read **read-only** throughout: every census probe, the before/after bodies,
the guard file and the sweep all read it and none wrote to it.

**Fixture-only children, named as such:** the degraded certificate states
(`absent`, `unreadable`, present-with-no-grade, zero-findings, REJECTED) are
reached by pointing `out_dir` at a pytest `tmp_path` and writing a small
`certificate.json` there. They live for the duration of one test and touch no
board.

**Committed artifacts written:** `tests/ai_exam/sweeps/2026-08-04-shared-body-v1/`
(transcript, sidecar, ledger, provenance report) and the rebuilt
`src/mre/corpus_index.json`.

## 11. Carry-forwards

Everything in the §9 ledger (S-01 … S-04), all owned by **R1**. The one a
session should take next is **S-02** — the gate's grade is in no evidence record,
so every surface that reads evidence alone is structurally unable to state it,
and the route in this session works around that rather than closing it. A Metric
or Artifact record emitted at the gate is the fix shape; it is a contract change
and wants a session, not a micro-session.

Untouched and still open as briefed: the (d.2) ladder work (D-03/D-04), Q7
itself (this session contributes §8 as one input line; the format decision is the
room's), teaching persistence pending the C9 founder round, and R2–R5.
