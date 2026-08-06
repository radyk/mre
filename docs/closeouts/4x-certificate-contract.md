# Session S-02 + S-03 — the certificate contract

**2026-08-05.** R-CT1 ruled and BUILT. Cross-room (the gate is R4 territory, the
voice is R1's; docs/07 §5b). Two ledger rows from the shared-body census closed,
one arbitrated decision executed, one predicate-audit instance settled.

**`CONTRACT_VERSION` unchanged at 1.15** — see §3.4, where the brief's stated
expectation of a bump is answered by a rule docs/02 already carries. docs/02
AMENDED (§4.4, §4.5, §6). **Parse prompt v19 and synthesis prompt v9 both
unchanged**: every seam here is gate code, contract text, authored copy or tests.

---

## 1. The census reconciliation — stated first, as the brief required

**THE CAUSE IS AN (e2) REPORTING ERROR, AND IT IS IDENTIFIABLE TO THE LINE.**

The standing ruler (`tools/spikes/teaching_graft_e2/census_precision.py`) reads
**5** non-GK firings where (e2)'s table recorded **2**, over the same 522-line
corpus. Four candidate causes were named in the brief — instrument change,
invocation change, corpus drift, or a reporting error. A 2×2 settles it, plus
the before-F1 instrument for completeness
(`scratchpad/reconcile_census.py`, `reconcile2.py`):

| instrument | corpus | unique / GK / non-GK | PB on GK | **PB on non-GK** |
|---|---|---|---|---|
| (e) `3f44004` — *before F1* | (e2)'s 50 transcripts | 522 / 121 / 401 | 2 | **5** |
| (e2) `50dfccb` — *after F1* | (e2)'s 50 transcripts | 522 / 121 / 401 | 3 | **5** |
| (e2) `50dfccb` | today's 54 | 526 / 122 / 404 | 3 | **5** |
| (d.3) `6bf0ed9` — HEAD | today's 54 | 526 / 122 / 404 | 4 | **5** |

**Every cell reads 5.** The GK column reproduces (e2)'s recorded 2 → 3 exactly,
and `floor_contradictions` is 0 in every cell, so the ruler and the corpus are
both behaving. It is therefore **not** an instrument change, **not** corpus
drift, and **not** the invocation.

**Where the 2 came from.** `tools/spikes/teaching_graft_e2/f1_widening_trial.py`
lines 90–92 count `_PRODUCT_BEHAVIOR_RES[0][1]` — **pattern (a) alone**, the
pattern F1 was widening — and print the result under its own `(context)` label.
Run today it still prints:

```
(context) firings on the 404 NON-GK claim lines: shipped 2 -> candidate 2
```

and exactly **2 of the 5** whole-predicate firings carry pattern (a)'s reason
(`it states what this product does`); the other three fire on (b) and (c). That
one-pattern context line was transcribed into a table whose other two rows are
`census_precision.py`'s — a **three**-pattern instrument. Within its own script
the 2 was correct. The error is the transcription.

**THE OPERATIVE PRECISION FIGURE IS 5** — of 401 on (e2)'s corpus, of 404 today.
Unchanged by F1, unchanged by (d.3)'s R2 widening.

**And a qualification that matters more than the number.** None of the 5 is a
live false positive. All five are `synthesis — read from: <ids>` lines, i.e.
CITED claims, and `product_behavior_disqualifiers` is consulted only under
`if not cited` (`claim_verifier.py`). Read them and they are all genuine
statements about this product's behaviour — the predicate is *right* about them;
they simply never reach it. The non-GK column measures reach, not error.

**The instrument is not at fault and needs no change.** §5a.222(c) is resolved
and closed. What generalises is the transcription lesson: **a script's
`(context)` line is not the measurement**, and two instruments' outputs placed in
one table under a shared heading is how a number stops meaning what it says.

---

## 2. S-02 — the gate's verdict enters the evidence

### 2.1 The gap, stated precisely

`ConformanceGate.record` emits a Finding **only** when a rule is not satisfied.
That is correct and it stays correct: every finding code names a defect, and a
satisfied rule is not one. **`record()`'s silence is not the bug.**

The consequence is the bug. An ACCEPTED submission with no deficiencies left the
evidence store **completely silent about its own certificate** — the grade was
computed by `grade_from_outcomes`, written to `certificate.json`, and never
reported. Every surface that reads evidence alone was therefore *structurally*
unable to state it: `Explainer._opener_certificate` returns `{"grade": None}`
and says so in its own docstring, and the certificate route had to reach past
the store to the artifact. The census session called that workaround honest and
ledgered the gap rather than papering over it. This closes it.

### 2.2 Which record kind — and the four refusals

The verdict is not one thing. It decomposes into three parts that each already
had a home in docs/02 §4:

| part | record | what carries it |
|---|---|---|
| the categorical verdict | **§4.5 Event** | `status_text: "gate_verdict"`, tier `headline`, subjects naming the submission; payload carries grade, costing grade, outcome tally, flags, counts, provenance |
| the coverage | **§4.4 Metric** | `gate.rules_checked` rolling up `gate.rules_{satisfied,flagged,degraded,violated}` |
| the artifact | **§4.6 Artifact** | `certificate.json` registered via verb 7 with its sha256 |

The in-repo precedent for the Event is M6's `solve_complete`, which carries that
module's terminal verdict — status, objective, gap, budget — and which both the
document assembler and the answer surface read. §5's rule is the licence:
*codes are for routing, payloads are for substance.*

**Refused, each for its own reason and each written into docs/02 so a later
session inherits the reasoning rather than re-deciding it:**

- **a Finding** — every code in the vocabulary names a problem, so an ACCEPTED
  grade would have to wear a defect's code. Category fusion.
- **a Decision** — the grade is a **pure function**, not a choice. There are no
  alternatives to enumerate, and `driver` is mandatory-exactly-one where every
  one of the 14 codes names a *scheduling* cause. Recording a computation as a
  Decision claims deliberation that did not happen.
- **a Metric for the grade itself** — `value` is a float. A grade is a word.
- **a new record type** — a seventh type to carry one categorical field is a
  larger change than the gap it closes.

### 2.3 Both exits, and why that is not belt-and-braces

`ConformanceGate.run` has two returns: the full rule cascade and the intake
refusal (the path for "I was pointed at nothing"). **An intake refusal is still
a grade** — REJECTED, C0, with its `intake_error` — and a planner asking what
the certificate says after one must be answerable from the store. A verdict
record present on only one path would have been a gap shaped exactly like the
one it was built to close. One emitter (`emit_gate_verdict`), two call sites,
and **NC1 and NC6 revert them independently**, so a fix landing at one exit
cannot pass.

### 2.4 Provenance, truthfully

`grade_provenance` carries `provenance_class: "derived"` and the formula id
`mre.contracts.ids_rules.grade_from_outcomes`. The grade is computed from rule
outcomes that are themselves observed off the submission; writing it as
`observed` would be the defect class the 2026-07-12 amendments name.

**It is a use of the docs/01 §7 vocabulary and NOT a sidecar write.** A sidecar
is keyed on `(entity_id, attribute_name, snapshot_id)` over the **canonical**
model, and M0 runs before canonical identities exist at all. The guard asserts
the formula id **resolves to a callable**, so the provenance is walkable rather
than decorative — a reader can go and read the function.

### 2.5 The read: one definition, one stated order

`Explainer._read_certificate` is the single definition, and the order is stated
in the code, not distributed among callers: **evidence first, artifact second.**
`source` names which reading answered, so no caller can be confused about what it
holds and the guards prove the order rather than infer it.

**The fallback is retained and is not a legacy path.** Evidence is append-only,
so every board gated before this commit has no verdict record and never will —
**NO RETROACTIVE WRITES**. Reading the artifact is the only honest way to answer
about those boards.

**THE PINNED-WORLDS LINE.** `_ai_exam_scratch/gb_pinned` (gated 2026-07-26) has
zero `gate_verdict` events; it reads `source: artifact` and still states its
grade, and `test_the_pinned_board_falls_on_the_artifact_side` asserts exactly
that on the real board. The two pinned rolling worlds (`rolling-c32a6140-b6b`,
`rolling-e9ccc879-a4b`) are on the same side of the line by the same rule and
were **not re-minted, re-solved or touched**. Every board minted from this commit
lands on the evidence side.

### 2.6 Live, both sides

Fenced world (`datasets/mobility_box`), full pipeline into scratch — the
**evidence** reading, citing its record:

```
SOURCE: evidence | record_id: 41116707-27d7-4a80-ba61-b94d19098938
grade: ACCEPTED C2 | rules: 29 {'satisfied': 29}
provenance: {'provenance_class': 'derived',
             'formula_id': 'mre.contracts.ids_rules.grade_from_outcomes',
             'inputs': 'rule_outcomes'}
```

The record as emitted, on a submission where **every rule is satisfied** — the
exact case that emitted nothing before:

```json
{"record_type": "event", "module": "M0", "tier": "headline",
 "subjects": [{"entity_id": "mobility_box", "entity_type": "submission",
               "system": "IDS"}],
 "message": "intake gate verdict: ACCEPTED (costing completeness C2, 29 rule(s) checked)",
 "status_text": "gate_verdict",
 "payload": {"grade": "ACCEPTED", "costing_completeness_grade": "C2",
             "rules_checked": 29, "outcome_tally": {"satisfied": 29}, ...}}
```

and its coverage metrics, decomposing exactly (the consolidator verified this at
`end()`, which is why the components are emitted **even at zero**):

```
gate.rules_satisfied  29.0 rules   gate.rules_flagged    0.0 rules
gate.rules_degraded    0.0 rules   gate.rules_violated   0.0 rules
gate.rules_checked    29.0 rules   rollup_of = the four above
```

### 2.7 The contract diff

`docs/02-evidence-contract-spec.md`, three hunks, **+22 / −4**:

| § | change |
|---|---|
| **§4.4 Metric** | one sentence added to the decomposability contract: a rollup's components are emitted **even at zero**, with M0's `gate.rules_*` named as the worked example, because components that appear only when non-empty cannot be verified as a set |
| **§4.5 Event** | `subjects` declared emittable (the field was always in the model; the verb hardcoded `[]`), then the M0 gate verdict in full: the gap, the three-record decomposition as a table, `grade_provenance`, and **the four refusals with their reasons** |
| **§6 verb set** | `record_event(status_text, payload=None, subjects=None)` |

The refusals are written into the spec deliberately. A later session asking
"why isn't the grade a Decision?" should find the answer in the contract rather
than re-litigate it from scratch — and, more to the point, should not be able to
*change* it without reading why.

### 2.8 A flaw found by checking rather than assuming

The first implementation took `verdicts[-1]` as "the most recent verdict", and
the first test asserted `cert["record_id"] == verdicts[-1]["record_id"]`.

**Both were wrong in the same way.** `EvidenceIndex.build` walks
`sorted(runs_dir.glob("*.jsonl"))` and run files are named `<uuid4>.jsonl`, so
index order *across runs* is effectively random — "last in the list" is the
lexicographically-last run id, not the newest one. And the test could not have
caught it: it asserted the implementation against its own list position, so it
passes under either rule. **A vacuous assertion, of the shape this repo keeps
naming.**

The route now sorts by the record's own `timestamp` (stable, so equal stamps
keep index order), and the test names the newest record by `max(...)` on the
timestamp and requires the route to have chosen *that* one — after asserting the
two runs are distinguishable in time at all, so the comparison cannot be
degenerate.

---

## 3. S-03 — the signing sentence goes, the capability parks

### 3.1 What was wrong with a true sentence

> *"This is the gate's own record, generated 2026-07-26, and it is unsigned —
> nobody has countersigned it."*

True of the artifact. False as an implication: it tells a planner a signing step
exists and was not taken, when this product has **no certificate-countersigning
concept at all**. The (e) review named the species — **the manufacture rule's
quieter cousin: asserting the absence of something implies the something.**

The cure is not a softer phrasing. It is a sentence about what the record *is*.

### 3.2 What replaced it

> *"This is the gate's own record, generated 2026-08-05; the grade is computed
> from those rule outcomes."*

Provenance, which is what the brief asked the answer to state, and it is
**checkable**: `grade_from_outcomes` is pure and the outcomes are the counts
printed one line above.

**The clause is stated only where the reading carries provenance.** A board read
from the artifact has none to quote and does not quote one —
`test_the_provenance_sentence_is_not_claimed_without_the_provenance`. That is a
body difference between old boards and new ones; it is named as a carry-forward
(§5a.226(d)) rather than smoothed over.

### 3.2a Before and after, both from live runs on the precedented board

`_ai_exam_scratch/gb_pinned`, read-only, same instrument both times. The BEFORE
is taken by reverting the S-03 seam **in bytes** and rendering; the restore was
verified byte-identical by sha256 *before* anything was printed
(`scratchpad/before_after.py`, the negative-control harness pattern).

**BEFORE** — sha256 `c48508b74fc723ae`:

```
Intake review: ACCEPTED — costing completeness C2.
29 gate check(s) ran against this submission: 29 satisfied.
No deficiencies, nothing normalized, nothing flagged.
This is the gate's own record, generated 2026-07-26, and it is unsigned — nobody has countersigned it.
```

**AFTER** — sha256 `11a9e65f4330d75e`:

```
Intake review: ACCEPTED — costing completeness C2.
29 gate check(s) ran against this submission: 29 satisfied.
No deficiencies, nothing normalized, nothing flagged.
This is the gate's own record, generated 2026-07-26.
```

**`c48508b74fc723ae` IS THE CENSUS SESSION'S OWN RECORDED FIGURE** for its
"after" body (that close-out §4.5). Reproducing it independently, from a
byte-revert rather than from the record, is what makes this a measured
before/after rather than a quoted one — the starting state is confirmed, not
assumed.

`data-problems` renders `39022447757c0386` in **both** runs — unchanged, and
again the census session's exact value, so the repaired pair stays repaired
across this change.

(This board is on the artifact side of the line, so it states no provenance
clause. The evidence-path body — the same route on a board gated after this
commit — is quoted in §2.6.)

### 3.3 The copy census

Repo-wide, excluding `node_modules`, `_data` and the corpus index: **13 lines
carry the signing vocabulary, and exactly one was live copy** — the site removed.
The rest:

| where | what it is |
|---|---|
| docs/04, docs/07, `4a-micro-shared-body-census.md`, the committed sweep transcripts | **historical record** of what was said. Correctly left alone — docs/04 is append-only and a sweep transcript is an artifact of a run that happened |
| `renderers.py:1536` | *"passed unsigned"* — a magnitude without an arithmetic sign |
| `tests/test_promotion.py:45` | promotion authority (R-AI5(5)), a different concept |
| `calibration.py`, `schedule_document.py` | **R-CAL1's `CalibrationProfile` signature** |

No sibling copy echoes it. The guard is asserted on **both** rendering paths,
because the removed sentence lived in the `present` branch and both readings
reach it — a fix proven on one of them is not proven.

### 3.4 The contract-version question, answered by an existing rule

The brief expected docs/02 to bump 1.15 → 1.16. **No `CONTRACT_VERSION` bump is
owed, and docs/02 §4.2 already states the rule** (written when `PLANNER_DIRECTIVE`
was added):

> *"The version constant `CONTRACT_VERSION` versions the **schedule document** —
> the read-only artifact the cockpit and the API render… A vocabulary change is
> instead governed by the add-never-repurpose rule… A bump **would** be owed if a
> driver code ever reached a document field; none does."*

Nothing added here reaches a schedule-document field: the records live in the
evidence store, which the document does not carry. So the ceremony performed is
the one the rule prescribes — the spec amended in the same commit as the code —
and the version constant is untouched. Stated rather than quietly diverged from.

### 3.5 R-CAL1 is untouched, and a guard says so

A `CalibrationProfile` signature is a **different artifact with a defined
attestation**: a human accepting a measurement they are answerable for, rule (2),
`--accept` needing `--by`. Nothing here weakens it and nothing here is precedent
against it. `test_r_cal1_is_untouched_by_s03` asserts rule (2) still holds, so a
future session reading S-03 cannot take it as licence.

### 3.6 The parking entry

In docs/07 §4 (Post-pilot sequence), pointer-form, no design, with Daryn's two
prerequisites verbatim:

> **(1) define what the signer is attesting to; (2) identify when customers
> actually require human approval.**

Nothing is built, scaffolded, or implied in copy anywhere.

---

## 4. Guards and controls

**`tests/test_certificate_contract.py` — 21 tests**, all green.
`tests/test_certificate_route.py` is **untouched** and still green (15),
including `test_deaf_is_silent_on_the_pair` and the two-bodies-differ assertion —
the census session's repair holds. The bodies on the pinned board:
certificate `11a9e65f4330d75e` (was `c48508b74fc723ae` before the signing clause
came out), `data-problems` **unchanged at `39022447757c0386`**, the census
session's exact value.

**6 negative controls proven RED**
(`tools/spikes/certificate_contract/negative_controls.py`), each asserted **GREEN
AT HEAD before its seam was reverted**, every restore **byte-identical by
sha256**, ANCHOR NOT FOUND a failure and never a skip:

| control | reverts |
|---|---|
| NC1 | the verdict emission at the **cascade** exit |
| NC6 | the verdict emission at the **intake-refusal** exit |
| NC2 | the route's evidence-**first** order |
| NC3 | the removed signing sentence, verbatim as it stood |
| NC4 | `Event` subjects (the common envelope) |
| NC5 | the artifact digest taken from the string rather than the file |

**NC4 STAYED GREEN ON ITS FIRST RUN, AND IT WAS THE CONTROL'S FAULT, NOT THE
SEAM'S.** Its anchor was the one-liner `subjects=subjects or [],` — which appears
in **`record_metric` first**, so a single-occurrence replace reverted the wrong
verb entirely and the envelope guard never noticed. Re-anchored on three lines
including `message=message or status_text`, unique to `record_event`, it goes
red. This is (d.2)'s lesson at a third site: a control that reverts something the
guard does not depend on proves nothing, and the only thing that finds it is
running the control and reading the output.

---

## 5. A defect the guard caught that reading the code would not have

The first version of the artifact registration hashed the JSON **string** it had
just serialized:

```python
digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
```

`Path.write_text` **newline-translates on Windows**, so the bytes on disk are not
the bytes of that string, and the registered digest did not verify against the
very artifact it named. It went red the moment a test compared the record's hash
to `path.read_bytes()`. Fixed by hashing the file after writing it.

**A digest must be taken from the artifact, not from the string we meant to
write.** This is the line-endings lesson (4A-(a), (e2) §6) arriving at a third
layer — not source files, not docs, but a hash we told a reader to trust.

---

## 6. Suites

Measured on **this tree**, unchunked.

| | result | wall |
|---|---|---|
| baseline — (d.3)'s measured after-run at HEAD `6bf0ed9` | **2882 passed / 305 skipped / 0 failed** | 15m11s |
| **after** | **2903 passed / 305 skipped / 0 failed** | 18m29s |

**+21 exactly, and NO RESIDUAL** — skips unchanged at 305, zero failures, nothing
else moved in either direction. Collection confirms the delta independently:
**3208 with the new guard file, 3187 without it**, and **3187 is byte-for-byte
the number (d.3) recorded**, so the baseline is the same tree in the same state.

**THE FIRST FULL RUN WAS KILLED AND RE-RUN, DELIBERATELY.** A flaw found
mid-suite (§2.8) changed `explainer.py` while that run was in flight, and pytest
had already imported the module — so its result would have described a tree that
no longer existed. The run of record is the second one, started only after the
source tree was final.

The corpus index was rebuilt **after** the docs/02, docs/04 and docs/07
amendments and **before** the suite — the ordering four previous sessions learned
the hard way, and now the pre-commit currency hook's job as well.

**Cockpit UNTOUCHED and not re-run** — no `src/cockpit/` file was opened.

---

## 7. Minted / untouched

- **MINTED NOTHING in `_data`.** No board was solved into the data root, no run
  registered, no schedule minted. `_data` is non-empty in this tree and was not
  written to.
- **Both pinned worlds read-only.** `gb_pinned` was read for the artifact-path
  bodies and the guard; neither pinned rolling board was opened.
- **Scratch children, named:** one fenced-world pipeline run and two gate-only
  runs under the session scratchpad, plus pytest `tmp_path` gate runs that live
  for the duration of one test. None touches a dataset or a registered world.
- New spike directory `tools/spikes/certificate_contract/` (the controls).

---

## 8. NOT FIXED, named

**(a) THE BOARD OPENER STILL RETURNS `grade: None`.**
`Explainer._opener_certificate` is the *named specimen* of the S-02 gap (the
4B.16 debt, §5a.49) — and the record it needs now exists. It is left alone
deliberately: the brief scoped the certificate ROUTE, and the opener is a
different surface with its own owner. What changed is that it is now a one-call
fix rather than a contract change.

**(b) THE VERDICT EVENT IS SUBJECT-REACHABLE ONLY ON A SCHEMA-2 INDEX.** A
schema-1 index dropped every subject-less record, and `_V1_LOST_CLASSES` still
names `event` for that reason — the class list stays true *of those files*. New
Events carry subjects, so the loss is historical. A bound, not a clean bill.

**(c) `certificate.md` IS WRITTEN BUT NOT REGISTERED.** The verdict record
references `certificate.json`, which is where the contract line is drawn; the
markdown rendering of the same certificate is an output nobody registered. One
line, not taken, because tidying an adjacent artifact is not this session's
scope.

**(d) THE TWO READING PATHS' BODIES DIFFER BY ONE CLAUSE** — the provenance
sentence, stated only where the reading carries provenance. Truthful, and named
so a future session does not "fix" it by making the artifact path assert what it
cannot read.

**(e) THE LIVE ROUTE SWEEP WAS NOT RE-RUN.** `sweep_shared_body_v1` grades
ROUTING, and routing is untouched by this session — the parse prompt is unchanged
at v19 and no intent moved. Its five expectations would pass unchanged, which is
the census session's own Q7 point (§8 of that close-out): the bank cannot see a
body. Every body claim here is asserted by the guard file instead. Stated as a
call, not an omission.

---

## 9. What a summary would undersell

**That the census's "workaround is honest" was exactly right, and still left the
product unable to speak.** The certificate route reading the artifact was never
wrong — the fact was on disk and the read was truthful. What was wrong is that
*the evidence store did not contain the gate's own verdict*, so every other
surface that stands on evidence was disabled by construction, and the only
surface that worked did so by stepping outside the contract. A gap like that
does not announce itself as a defect: everything visible looks fine, and the cost
is paid by the answers nobody has written yet. It took a census of shared bodies
to notice, and it took this session to make the evidence contract true of its own
first module.

**And that S-03 is a smaller edit than it looks and a larger rule than it
sounds.** One sentence, one site. But the sentence was *true*, and it was removed
anyway, because a true statement about an artifact ("it has no signature") licenses
a false inference about the product ("so someone was supposed to sign it"). The
repo already had the manufacture rule for claims about the plant. This is the
same rule turned on claims about *ourselves*: **we do not describe our product by
what it lacks, because a planner cannot tell the difference between a gap and an
omission.** The arbitration — remove, do not build, do not scaffold — is what
keeps that from becoming a roadmap item nobody asked for.
