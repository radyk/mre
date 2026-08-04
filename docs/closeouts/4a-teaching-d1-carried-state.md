# Session 4A teaching-graft (d.1) — carried answer state

**2026-08-04.** R1 item 2, session (d.1) (docs/07 §5b). The (d.0) recon measured
what conversation state exists and ruled nothing; this session fixes ONE family
from its ledger — **what the product keeps from the last turn, what it does with
it, and whether it says so.**

Two rulings landed in `docs/04-design-history.md` verbatim: **R-MT1** (carried
answer state is schedule-scoped, cleared on rebind, honest about its own absence)
and **R-LD5** (disclosure follows the subject, not the resolver). Both were
arbitrated before the session opened.

Contract unchanged **1.15**. Parse prompt unchanged **v18**, synthesis prompt
unchanged **v8** — every fix here is deterministic-seam work, and none of it
needed a prompt. No docs/06 doorway is owed: nothing here is a declared fact
about a plant.

---

## 1. Measurement 0 — the recon's inference is now an observation

**D-05's browser half is CONFIRMED.** The dossier's §12.3 named this the single
highest-value thing to check before scoping, and it was checked first, against
HEAD, before any source changed.

`tests/cockpit/carriedstate.spec.mjs` boots the shipped cockpit on a real board,
asks a question, drives a real `drag.accept()` — the same gesture
`gesture.spec.mjs` uses, which mints a child version and calls `onVersionChange`
— and reads what the next `/ask` request carries. At HEAD:

```
POST /schedules/sched-multi-route-distinct-edit/ask
  history: [ { question: "why is ORD-000003 on F001-RES001?",
               resolved_question: "why is ORD-000003 on F001-RES001?",
               route: null, order: null, machine: null, op_seq: null } ]
```

**The child's url, the parent's turn.** The recon's inference from
`main.js:745-754` was right, and the gesture that reaches the server defect is
the one a planner performs every time they accept an edit.

The recon's scoping honesty held in the other direction too: the schedule PICKER
path is a full `location.assign` reload and starts an empty conversation with a
fresh session id. That is now asserted rather than assumed, so the client half of
R-MT1 cannot quietly change it.

**Stale-process check.** No serving process existed: `curl -s -m 3
http://localhost:8000/health` → exit 7, `Get-Process python*,uvicorn*` → empty.
Every Python measurement is in-process from the working tree; every browser
measurement is against a `vite build` of the tree performed by the harness's own
`webServer` step, so the bytes under test are the tree's by construction.

---

## 2. The order of work, and why it was that order

W1 (the store key) landed before W4 (the drill-down wire), per the brief.
Wiring the drill-down to `ANSWER_MEMORY` first would have widened the
cross-board surface from one gesture to two. In the event this mattered: the
drill-down now reads the same stores prove-it does, and every one of those reads
was schedule-scoped before the first of them existed.

---

## 3. The store-key census, re-run at fix time

Not inherited from the dossier. Grepped by name over `src/` after the change;
every site listed with what it does now.

**`AnswerMemory` / `ANSWER_MEMORY`**

| site | role | scoped |
|---|---|---|
| `interpreter.py:2149` (`run_ask`) | the ONE write seam | yes |
| `interpreter.py:1640` (`dispatch`, prove-it) | read | yes |
| `interpreter.py:1773` (`dispatch`, drill-down) | read — NEW this session | yes |
| `interpreter.py:1644`, `:1776` | `held_elsewhere` — R-MT1 clause 3's input | yes |
| `interpreter.py:1198` (`forget_deliveries`) | clear | by SESSION, all boards |

**`SynthesisMemory` / `SYNTHESIS_MEMORY`**

| site | role | scoped |
|---|---|---|
| `interpreter.py:1433` (`_synthesis_dispatch`) | write | yes |
| `interpreter.py:1613` (`dispatch`, prove-it) | read | yes |
| `interpreter.py:1767` (`dispatch`, drill-down) | read — NEW this session | yes |
| `interpreter.py:2126` (`run_ask`) | staleness forget on a later route | by session |
| `interpreter.py:1199` (`forget_deliveries`) | clear — **ADDED this session** | by session |

**`_DELIVERED`**

| site | role | scoped |
|---|---|---|
| `interpreter.py:2002` (`dispatch` tail) | write | yes |
| `interpreter.py:1322` (`bundle_repeat`) | read | yes |
| `interpreter.py:1197` (`forget_deliveries`) | clear | by SESSION, all boards |

**`ParseMemory`** — unchanged, and stated because the census is what shows why:
`ParseMemory.key` has carried `"sched"` since 4B.5. It is the reason the parse
cache was never part of this defect, and the reason the fix is a key and not a
new mechanism.

**One thing the census found that no test had.** `forget_deliveries`' own
docstring has called itself *"the ONE place that clears server-side conversation
state"* since 4B.22 — and there were THREE such stores and it cleared TWO.
`SYNTHESIS_MEMORY` survived every RESET, so a `prove it` on the first synthesis
turn of the next conversation could ground a claim from a conversation the bank
had already thrown away. That is 4B.16a's fifth channel, at the store added one
session after it. Fixed in the same commit and named here rather than folded into
the ruling, because it is a gap the ruling did not predict.

---

## 4. Before and after, quoted verbatim from live runs

All against the two pinned boards, read-only, through the recon's own harness
(`tools/spikes/teaching_graft_d1/after.py`, which imports
`tools/spikes/multiturn_recon/conv.py`) so before and after are the same
instrument.

### 4.1 P4 — the cross-version bleed (R-MT1)

**BEFORE** (d.0 dossier §5, board A `rolling-db5395dc-2ae` → board B
`rolling-c362baa4-1b0`):

> That was my answer to "how many orders are late and what is the total
> tardiness cost". It came from a contracted route, so it has no per-sentence
> claims to pick apart — here is the whole record set it was assembled from
> (102 record(s)):
>
> - lateness_minutes = 5297.0 min for ORD-000001  [record: 2aafb20c…]
> - lateness_minutes = 10849.0 min for ORD-000002  [record: 06e09705…]
> … *(100 more)*

Board B has 40 known orders, 26 scheduled, and **nothing late**.

**AFTER**, same sequence, server-only arm (`clear_client=False` — the gesture as
the recon measured it, so clause 1 is proven without clause 2 helping):

```
T1 [2ae]  route=late-orders  records=102
T2 [1b0]  route=prove-it     records=0
   The answer you're pointing at was about the PREVIOUS VERSION of this plan —
   the board was replaced between that turn and this one, so its records
   describe a schedule you are no longer looking at and I won't open them
   against this one. Ask it again here and I'll ground the answer on this
   version.
```

**Records: 102 → 0.** Direction B→A is identical in shape.

**AFTER**, shipped arm (clause 2 active, the client cleared): T2 parses as
CLARIFY — with the conversation cleared, *"show me the evidence for that"*
genuinely has no referent, and saying so is the right answer.

### 4.2 P8 T2 — the drill-down (D-01)

**BEFORE** (d.0 §7), one turn after a good teaching answer about frozen zones
that cited ORD-000209:

> ```
>   CUT-01 is in a workload too dense to schedule cleanly  [WARNING]
>        Affected: CUT-01
> [rendered by: template | register: testimony]
> ```

**AFTER**:

```
T1 [2ae] route=synthesis  claims=4  reads=[lateness_set, fetch_record,
                                           placements_for_order, machine_occupancy]
T2 [2ae] route=drill-down records=1
   That part is my inference, not a record — here is each thing I read to get
   there:
```

### 4.3 P2b middle arm — the subject nobody named (R-LD5)

**BEFORE** (d.0 §4.2): `source: utterance`, resolution note **empty**.

**AFTER**:

```
subjects=[{kind: order, raw: ORD-000073, ref: ORD-000073,
           source: conversation, pointed: True, op_seq: 10}]
note = "resolved against ORD-000073 (read from what you asked earlier — you
        didn't name it in this question); and about op10, read from your
        earlier question"
```

**True negatives held.** The cold arm and the after-unrelated arm both still
reach CLARIFY with an **empty** note — there is genuinely nothing to bind, and a
planner is never told back what they just said.

### 4.4 The zero-record control (D-06)

**BEFORE** (d.0 `zero-record-control.json`, one board, two turns), about a real
`late-orders` testimony answer that cited nothing because nothing on that board
is late:

> My answer to "…" was **authored copy** — it states what this product can and
> can't do, not a fact read off a record — so there is nothing behind it to open.

**AFTER**:

> My answer to "how many orders are late and what is the total tardiness cost"
> came from **late-orders, which answers from this plan** — but it attached no
> records of its own, so there is nothing here for me to open. That is a
> different thing from it being a statement about what this product can do: it
> read the board and cited nothing.

The capability sentence is not gone; it is now reached only from
`PRODUCT_META_ROUTES`, and a CLARIFY still gets it (`test_second_question.py::
TestDrillDownAfterCapabilityCopy`).

### 4.5 The deaf pair (D-07) — and the P6 T7 true positive

**BEFORE** (d.0 `deaf-control.json` T2): the deictic follow-up was told *"I'm not
understanding what you're asking"*.

**AFTER**, live, both sides, from `sweep_carried_state_v1` block E:

```
E1  Q: so why is it there        followup=deepen  route=why-here (SAME)
    -> body byte-identical to the previous turn, NO rider

E2  Q: what does the certificate say   followup=deepen
    prior route data-problems, this route certificate-testimony (DIFFERENT)
    -> "I've now given you this same answer for two different questions, which
        probably means I'm not understanding what you're asking. Last time you
        asked: 'are there any data quality problems'."
```

---

## 5. The defect this session introduced, and the thing that caught it

**The first version of the D-07 gate suppressed the one true positive `deaf` has
ever produced, and the unit test was green the whole time.**

The gate as first written read `followup_of in (DEEPEN, LIST_EXPAND)` and
returned. The live parse marks *"what does the certificate say"*, asked after
*"are there any data quality problems"*, as `followup=deepen` — reasonably,
because it does follow. So the rider stayed silent on exactly the specimen the
brief named as the guard that matters. `sweep_carried_state_v1` block E2 showed
it; `test_carried_answer_state.py::TestDeafGate::test_the_P6_T7_true_positive_
STILL_FIRES` did not, because it constructed `followup_of=NONE`.

**A guard that supplies its own arguments proves the assembler, not the path** —
4B.21 §5a.78, at a seam built in the same session that quotes it.

The fix is per-row and reads the ROUTE the prior delivery came from, which
`_DELIVERED` has carried since 4B.15: same route means the planner deepened and
the answer is correctly the same; different route means two questions collapsed
onto one body, which is what `deaf` is for. A second guard now constructs the
LIVE shape (`followup_of=DEEPEN` on the certificate turn) and a second negative
control **(f2)** reverts to the first draft specifically.

**A second one, same shape, found the same way.** Wired to the ANSWER memory
alone, a drill-down onto a SYNTHESIS answer fell to its record set — empty,
because an R-TG1 general-knowledge claim carries no records by design — and told
the planner their teaching answer had cited nothing. Caught in this session's own
live P8 run, not by a test. Both gestures now reach the same two stores in the
same order.

---

## 6. What landed, W1–W8

* **W1** — `AnswerMemory`, `SynthesisMemory` and `_DELIVERED` key on
  `(session_id, schedule_id)`; `forget` is by session and takes every board;
  `held_elsewhere` answers the one question the composite key cannot.
  **D-11**: `_DELIVERED` gained the LRU-32 session bound its two siblings had.
* **W2** — `panel.clearConversation()` clears `askHistory` and `lastAnswered`;
  `onVersionChange` calls it beside `clearSelection`. **The session id survives**,
  stated in the code with its reason: once the stores key on (session, schedule)
  it can reach nothing from the old board, and re-minting one on every accept
  would fragment the question ledger's own session thread (R-AI5(5)). The
  rendered turns stay on screen — they are a record of what was said.
* **W3** — `PROVE_IT_PRIOR_OTHER_VERSION`, authored copy, reached from both
  prove-it and drill-down.
* **W4** — the drill-down wire and the refusal half. `route_params` carries
  `claim` and `prior`; `_explain_drill_down` keeps its ordinal branch and
  delegates everything else to `_prove_it_bundle`, so the two gestures are one
  assembler rather than two that agree. `drill-down` joins `_NOT_REMEMBERED` and
  the synthesis-staleness exemption.
* **W5** — `prove_it_case` is the one definition of the six branches, read by the
  assembler and by the guard; the renderer branches on its value and never
  re-derives one from a record count.
* **W6** — `SubjectSource.CONVERSATION`; `_subject_note` gains a branch;
  `named_op_seq_source` carries the grain's channel by the same walk as the
  grain, so the two can never be attributed differently; `_with_assumptions`
  discloses it in the two shapes the honest sentence needs.
* **W7** — the deaf gate, per-row, reading `followup_of` AND the prior route.
* **W8** — **D-09** the outage turn renders as a system marker and is KEPT in
  the window (the planner can still see it on screen; dropping it would
  renumber the four turns they read); **D-08** the harness's history append moved
  under the success guard; **D-10** `_repeat_depth` deleted.

### The SubjectSource census

Three readers, all handled: `_subject_note` (`interpreter.py:440-458`, the new
branch), `route_params` via `named_op_seq_source` (new, the grain), and
`app.py:2096`, which serializes `s.source.value` and is value-agnostic. There is
no fourth — `_with_assumptions` reads `params["op_seq_source"]`, a string this
session now sets from the enum, not the enum itself.

---

## 7. Verification

**Python. Baseline 2658 passed / 305 skipped / 0 failed. After 2700 / 305 / 0.
Delta +42 passed, and it is accounted for file by file:**

| file | delta | what |
|---|---|---|
| `tests/test_carried_answer_state.py` | **+39** | new — the guard file |
| `tests/test_second_question.py` | **+2** | `TestDrillDownAfterCapabilityCopy` (the CLARIFY arm; the `PRODUCT_META_ROUTES` membership) |
| `tests/test_conversational_riders.py` | **+1** | `test_the_helper_that_lost_its_caller_is_gone` (D-10) |
| everything else | 0 | signature updates only |

Collection confirms it independently: **2963 → 3005**, +42. The per-chunk deltas
are +40 / 0 / 0 / +2, which is the same table read the other way. **Five test
bodies were UPDATED rather than added**, because they state the old behaviour and
the update IS the ruling: three `.last(session)` / `remember_delivery(...)` call
sites gained the schedule argument, `TestDrillDownAfterAnAnswerThatCitesNothing`
now asserts the empty-read sentence instead of the capability one, and
`TestRepeatLead`'s two `_repeat_depth` tests were rewritten against the live
`bundle_repeat`.

**THREE THINGS ABOUT HOW THIS WAS MEASURED, AND NONE OF THEM ARE ROUNDED OFF.**

**(1) Two baseline attempts were discarded.** The first was launched in the main
tree and overlapped this session's own edits (it returned 2657/305/**1**, a
`test_relevance_guard` failure caused by editing `renderers.py` mid-run). The
second was launched in a detached worktree that — because `mre` is an editable
install pointing at `C:\dev\mre\src` — **still imported the EDITED source**, and
returned 11 failures that were this session's own half-finished changes read
against HEAD's tests. A third, with `PYTHONPATH` pinned to the worktree, returned
2625/309 — still wrong, because a fresh checkout has no `_data` and collects 29
fewer tests. The number of record is the fourth, with `_data` junctioned in and
`PYTHONPATH` pinned; it collects **2963**, exactly what the main tree collected at
HEAD, and it reproduces the (c2) close-out's recorded 2658/305/0 to the test.

**(2) Both runs are CHUNKED, and the chunks are identical on both sides.** The
environment killed three consecutive full-suite background runs at 19%, 19% and
7%; the runs are therefore four alphabetical slices each
(`test_[a-e]`, `[f-m]`, `[n-r]`, `[s-z]` + `ai_exam` + `cockpit`), summed. The
sums equal the collection counts exactly on both sides, so nothing was dropped or
double-counted. **What a chunked run does NOT reproduce is cross-file ordering
and contention**, which matters in this repo — `test_n3000` and the
parallel-load flake class are contention-sensitive by record. Said rather than
glossed: the counts are exact, the load profile is not the same as one run's.

**(3) `--runslow` NOT run and not claimed either way.** (c)'s known red
(`test_ai_voice.py::test_cu5_split_jobs`) is a live-PARSE routing outcome; this
session changed neither prompt, but it did change the ask path, so the honest
statement is that it was not measured.

**Cockpit.** `367 passed / 2 failed of 369`. The 2 are the known deictic pair
(`cockpit.spec.mjs:111`, red at HEAD since 4B.23); the baseline is 365/2 of 367
and the +2 are this session's own spec. No new flake.

**Nine negative controls, every one proven RED against physically reverted code,
every restore byte-identical by sha256** (`tools/spikes/teaching_graft_d1/
controls.py`, plus the client-half one driven separately):

| control | target goes RED | control set stays GREEN |
|---|---|---|
| (a) the store key loses the schedule | ✅ | ✅ |
| (b) the drill-down loses its wire | ✅ | ✅ |
| (c) the `findings[0]` default comes back | ✅ | ✅ |
| (d) the prove-it branch is decided by record count | ✅ | ✅ |
| (e) a model-recovered subject reports UTTERANCE | ✅ | ✅ |
| (f) the deaf gate stops reading `followup_of` | ✅ | ✅ |
| (f2) the deaf gate reads `followup_of` ALONE | ✅ | ✅ |
| (g) the harness records an errored turn | ✅ | ✅ |
| (h) `onVersionChange` clears nothing else (cockpit) | ✅ | — |

**The control harness found its own bug first, and it is the mixed-line-endings
class from the other side.** 4A teaching-graft (a) met it on the WRITE
(`write_text` translated newlines and rewrote a whole file); this harness met it
on the MATCH — `explainer.py` is pure CRLF and `interpreter.py` pure LF, so
LF-joined multi-line anchors found nothing in half the files. Controls (c) and
(d) reported **ANCHOR NOT FOUND** on their first run, which is the only reason it
was noticed; a harness that had skipped them would have reported seven passes.
The anchor is translated to the file's own ending now, and the harness asserts
the edit took before running anything.

---

## 8. The bank, and the Q7 input it produced

`tests/ai_exam/banks/sweep_carried_state_v1.txt`, six blocks, 16 questions, run
live against the demo board `rolling-db5395dc-2ae`: **14/15 graded expectations
met**, one known miss documented in the bank itself. 18 parses, 0 retries, 0
malformed, 0 clarifies; two synthesis answers, 4 claims (2 interpretive, 2
general-knowledge, 0 cut, 0 ungrounded-load-bearing); route latency median
1801ms, synthesis median 24537ms. Transcript and sidecar at
`tests/ai_exam/sweeps/2026-08-04-carried-state-v1/`.

**The bank was run TWICE and both runs are part of the result.** The first
(13/15) is what exposed the deaf gate's own defect, §5; the committed transcript
is the re-run against the fixed gate. The first run is not preserved as an
artifact — its finding is §5 and the transcript would only duplicate it — and
that is stated rather than left to look like a single clean pass.

**Counts per family, and what the format could hold for each:**

| block | met | what it grades | what it cannot |
|---|---|---|---|
| A drill-down wired | **3/3** | the three routes of the sequence | that turn 2 opened turn 1's records |
| B the other phrasing | **2/2** | both routes | that both opened the same object |
| C the cold refusal | **0/1** | the route (known miss, below) | that it did NOT open the worst finding |
| D the unnamed subject | **3/3** | routing + the CLARIFY true negative | the disclosure line |
| E the deaf pair | **4/4** | all four routes | whether the rider fired |
| F which kind of nothing | **2/2** | both routes | which sentence was said |

**E is the block worth reading twice.** All four of its routes were MET in the
first run too — and in that run the rider was silent on E2, which is the defect.
Nothing in the graded column moved between the two runs; the whole of §5 is
invisible to the sweep's own score and was found by reading the transcript.

**The founding specimen is not encodable at all.** An exam run targets ONE
schedule — `RunTarget` is resolved once — and the grammar has no directive that
rebinds the board mid-conversation. R-MT1's own P4 pair is therefore not a
missing `EXPECT` key but a missing world. That is the strongest single input this
session has for Q7, and it is stated here rather than designed around.

Two smaller inputs, both found by writing the file rather than by reasoning about
it. `EXPECT`'s eight keys are every one a property of ONE turn's parse, so no
expectation can reference an earlier turn's content — every "grounding" assertion
above lives in `tests/test_carried_answer_state.py`, over two consecutive
`run_ask` calls, and in §4's quoted live runs. And **no expectation can say what
a turn did NOT do**: "the drill-down opened nothing" and "the drill-down opened
the wrong thing" are the same `EXPECT` line, which is precisely the distinction
D-01 turns on.

**The one miss is kept rather than fitted.** Block C expects
`route=drill-down` on a cold *"can you show me that on my board"*; the live parse
reads it as `unmatched` at confidence 0.25 and the second tier answers honestly
with the capability card. That is a good answer, and the property the probe
grades — that a cold "show me that" never opens the board's worst gate finding —
is true on both paths. Rewriting the expectation would hide that two different
mechanisms are keeping one property true.

Block D's expectation WAS corrected, and the correction is not a fit: it read
`clarify=no-subject` and the parse emits no clarify payload at all (the CLARIFY
comes from the dispatch's subject-resolution guard). The key graded the wrong
field; `route=CLARIFY` grades the right one.

---

## 9. What a summary would undersell

**That the sharpest fix in this session is a deletion of a default.** D-01 reads
as a wiring bug — a parameter with a docstring and no caller — and the wire is
the smaller half. The larger half is that with nothing to open, the route USED TO
PICK SOMETHING. On this board the something was a WARNING about a machine, served
in the register of testimony, one turn after a conversation about frozen zones.
A planner reading that has no way to know they were handed a default. The wire
makes the good case good; deleting the default is what makes the bad case honest,
and it holds on every board where the wire has nothing to deliver.

**That two of this session's own fixes were wrong on their first draft, and the
same instrument caught both.** Neither was caught by a unit test. The deaf gate
was caught by a SWEEP against a live parse; the drill-down's store ordering was
caught by a LIVE probe run. Both were green under tests that supplied their own
arguments. This repo has named that species before (4B.21 §5a.78, 4B.28 §5a.123);
what is new here is that both instances were introduced and found inside one
session, which is the cheapest possible place to find them and is only cheap
because the session runs live probes at all.

**That R-LD5 is a correction to how this product describes itself, not only to
what it says.** The (d.0) dossier's own §10 put it best: the resolution ladder is
documented across six sessions, a docs/04 amendment and four named rungs, and it
was empty on all four rungs for all six turns of P1 while the conversation worked
anyway — because the parse model reads the RECENT TURNS block and recovers the
subject itself. **The product's cross-turn understanding is a model behaviour
wearing deterministic clothes, and the clothes are why nothing disclosed it.**
R-LD5 does not change which mechanism resolves; it stops the deterministic
vocabulary from being used to describe a resolution it did not make.

**That the honest sentence for the empty read had to be written twice.** The
first version said the prior answer *"came from {route}, a contracted route that
reads this plan directly"* — and the first live run put `synthesis` in that slot,
which is not a contracted route. Caught in §4.2's own transcript, one line above
the result it was there to demonstrate.

---

## 10. Minted

**Nothing in `_data`.** Both pinned boards read-only; no schedule, run, snapshot
or registry row.

**Two expected children in the hermetic cockpit harness**, named rather than
glossed: `sched-multi-route-distinct-edit` (minted by the Measurement-0 accept)
and its equivalents in the negative-control re-runs. They exist only inside the
Playwright fixture server's in-memory lifecycle, which
`POST /__test__/reset` clears before every boot; nothing is written to disk.

The exam sweep wrote `tests/ai_exam/sweeps/2026-08-04-carried-state-v1/`
(transcript + sidecar), which is committed evidence.

---

## 11. Carry-forwards

Full list in docs/07 §5a.186. The two a session should take next:

**THE BANK CANNOT REACH THE FOUNDING SPECIMEN** (§8). Until Q7 is settled, R-MT1
is guarded by unit tests and a spike, and every future regression in it is
invisible to the sweep. This is now the concrete cost of Q7 rather than a
hypothetical one.

**D-03 AND D-04 ARE UNTOUCHED.** `last_answered_subject` covers 5 of the 33
`subject_type` literals in `explainer.py`, and `askHistory`'s `order`/`machine`/
`op_seq` are filled from the live board SELECTION rather than the turn's own
subject — so the ladder rung built to carry a typed subject is empty after most
answers, in a typed conversation, structurally. Session (d.2), after Q7.

Also named: `PRODUCT_META_ROUTES` is a judgement about four route ids that
nothing can derive; R-MT1 clause 3 has no live specimen from the SHIPPED client
by construction (clause 2 clears the channels first), so it is measured only on
the `clear_client=False` arm; the cold drill-down refusal is unreachable from a
live parse; and **the shared-body defect `deaf` caught is still live** —
`certificate-testimony` and `data-problems` render the same body, so the
certificate route does not state the certificate. That is a single-turn finding
and it goes to the shared-body census micro-session, which this session did not
open.
