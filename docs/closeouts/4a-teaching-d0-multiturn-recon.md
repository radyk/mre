# Session 4A teaching-graft (d.0) — multi-turn recon

**2026-08-04.** R1 item 2, session (d) of four, RECON half. docs/07 §5b R1 item 2(d)
says *"multi-turn grounding — RECON FIRST (measure what conversation state exists
before scoping)"*. This is that measurement.

**NOTHING WAS RULED, NOTHING WAS FIXED, NO PRODUCT SOURCE CHANGED, NO PROMPT WAS
BUMPED, NO BANK WAS TOUCHED.** Parse prompt stays **v18**, synthesis prompt **v8**,
contract **1.15**. No docs/04 amendment — recon rules nothing. The scoping session
(d.1) is drafted in chat FROM this dossier, not by this session.

Everything below carries a probe id and an artifact path under
`tools/spikes/multiturn_recon/artifacts/`. Where a statement is an inference from
code rather than an observation, it says **INFERENCE**.

---

## 1. The stale-process verification, stated

**There was no serving process, by construction, and that is how it was verified.**

* Every live number in this dossier comes from `mre.modules.interpreter.run_ask`
  driven **IN-PROCESS** from the working tree at HEAD `e10376b`, through the spike
  harness `tools/spikes/multiturn_recon/conv.py`. No HTTP, no uvicorn, no
  long-lived worker. Python imports the tree's `src/` on every invocation, so the
  code under measurement is HEAD's by definition.
* Checked anyway, because the stale-process class has three prior appearances
  (docs/07 §5b R4 item 4): `curl -s -m 3 http://localhost:8000/health` →
  **exit 7, connection refused**; `Get-Process python*,uvicorn*` → **empty**.
  Nothing was serving.
* `git status` at start and at measurement time: clean but for the untracked
  `RECON_GATEHOUSE.txt` (pre-existing) and this session's own spike directory.

The one thing this buys and the one thing it does not: it removes the stale-process
hazard for the **Python ask path**, which is all this session measured. **The
COCKPIT was not driven at all** — see §8 and the ledger row D-11.

---

## 2. The state map (Part A)

Every piece of conversation state that exists at HEAD. "Planner-visible" means a
planner can SEE it, not merely be affected by it.

| # | Name | Constructed | Stored | Scope | Lifetime / eviction | Readers | Planner-visible |
|---|------|-------------|--------|-------|---------------------|---------|-----------------|
| A1 | `askHistory` | `askpanel.js:33`, pushed at `:272` **after a successful answer only** | client memory; **last 4 sent** per request (`:247`) | ask-panel instance | grows unbounded in memory; a full page reload clears it | 7 server sites, §2.1 | the turns are on screen; what is SENT is not |
| A2 | `ANSWER_MEMORY` | `interpreter.py:272` | server process, `{session_id: {route, question, records}}` | session | LRU, **limit 32 sessions**; holds **1 turn** each; cleared by `forget_deliveries` | **exactly one** — the `prove-it` branch, `interpreter.py:1428` | only through a prove-it answer |
| A2b | `SYNTHESIS_MEMORY` | `interpreter.py:205` | server process | session | LRU 32; holds **1 answer**; **forgotten the moment any non-synthesis route answers** (`:1870`) | `prove-it` branch, `:1409` | only through prove-it |
| A2c | `_DELIVERED` | `interpreter.py:988` | server process, module dict | session | keeps **4** rows per session; **no cap on the NUMBER of sessions** | `bundle_repeat`, `:1122` | as the `deaf` rider's sentence |
| A3 | `ParseMemory` / `PARSE_MEMORY` | `interpreter.py:284` | server process | (question × context × session × **schedule**) | LRU 64; consumed by `take` | `run_ask:1825`, `_preflight:1935` | no |
| A4 | `last_answered_subject` | `askpanel.js:283` from `resolvedSubject(bundle)` | client memory, 1 turn | ask-panel instance | **overwritten every turn**, including by a turn that resolves to `{}` | `render_context` (both prompts), `_bind_from_context` | no |
| A5 | `selection` | `askpanel.js:71` off the live board | client | board | until the planner clicks elsewhere; **cleared on a version change** (`main.js:748`) | `render_context`, `_bind_from_context`, `_apply_mobility_floor`, `route_params:1596` | yes — the scope chip |
| A6 | `card` | drag controller → `askpanel.js:49` | client | one priced move | cleared on dismiss/accept/supersede | `describe_card`, `_bind_from_context` (top rung), `open-card` route | yes — the card |
| A7 | `session_id` | `askpanel.js:32`, `sess-<8 random chars>` | client, sent every request | ask-panel instance | **never ends**; a reload mints a new one | keys A2/A2b/A2c/A3 | **no** — rendered nowhere |
| A8 | question ledger | `app.py:2010` | **disk** (`_data/ledger`) | forever | append-only | **nothing at answer time**; only `/ledger/refusals` (DEV) and the offline promotion tools | no |
| A9 | pedagogical state | — | — | — | — | — | — |

### 2.1 The census of `history` readers — seven sites, and no eighth

Grepped by the **field name**, not the type, per the session's own discipline
(`grep -rn 'get("history")' src/mre/`):

1. `ParseMemory.key:320` — cache key; **questions only, last 4**.
2. `_repeat_depth:951` — **DEAD ON THE PRODUCT PATH.** No `src/` caller; only
   `tests/test_conversational_riders.py` exercises it. Its own docstring already
   says *"Callers must use `bundle_repeat`"*. Ledger row D-10.
3. `bundle_repeat:1109` — the repeat/deaf signal, last **2** turns.
4. `route_params:1591` — `params["prior_question"]` from `history[-1]`, **for
   `Intent.ATTRIBUTE_LOOKUP` only**. This is the ONLY route that reads a previous
   turn's TEXT into an answer.
5. `question_parser.render_context:163` — the prompt block, last **4**.
6. `question_parser._bind_from_context:289` — the ladder's HISTORY rung.
7. `explainer.py:886` — `_explain_drill_down(target, params.get("history"))`.
   **`route_params` never sets `params["history"]`, so this argument is always
   `None`.** See §7 / ledger row D-01.

There is no eighth. `last_answered_subject` and `selection` were swept the same way
(3 and 4 sites respectively, all listed in the table above).

### 2.2 A3 — `resolve_followup` is gone, and what replaced it is NOT the ladder

**The docs are stale on this topic exactly as the brief warned, but not in the
direction it suggested.** docs/04's 4A.1 CU2 describes `resolve_followup` doing
deterministic ellipsis resolution BEFORE routing. That function is deleted (R-AI5,
`interpreter.py` module docstring says so). Its behaviours were re-declared as
fields of `ParsedQuestion`.

What is live: the model parses first; a subject the model marks `from_context`
is bound by `_bind_from_context` on the fixed ladder **card > selection >
last-answer > history**; and *if every rung is empty*, `bind_subjects:325` falls
back to resolving **the words the model put in `raw`**.

**That fallback is the load-bearing path, and P1 proves it.** See §4.

**Visibility is NOT lost for a ladder resolution and IS lost for a model
resolution** — §4.2. That asymmetry is the single most consequential finding in
this dossier.

### 2.3 A4 / A5 — what reaches each tier

Both tiers render the SAME context block: `synthesizer.render_context` is a
one-line delegation to `question_parser.render_context` (`synthesizer.py:80-84`).
Measured verbatim from a captured payload (`p1-turns.json`, T6
`synthesis_prompt`):

```
CONVERSATION CONTEXT:
  OPEN DELTA CARD: none — no priced move is showing.
  BOARD SELECTION (what is highlighted right now): none
  SUBJECT OF THE PREVIOUS ANSWER: none
  PLAN REFERENCE DATE: 2026-01-05 (a Monday)
  HORIZON: 2026-01-05 to 2026-02-05 — a bare weekday name is AMBIGUOUS ...
  RECENT TURNS (oldest first):
    planner asked: "why is that"  -> answered with intent: CLARIFY
    planner asked: "why is ORD-000128 op20 placed where it is"  -> answered with intent: why-here
    planner asked: "what would have to change"  -> answered with intent: what-would-change
    planner asked: "how does a frozen zone normally work on a board"  -> answered with intent: synthesis
```

So, per turn, **each tier receives the previous four QUESTIONS and the ROUTE ID
that answered each.** It receives **no answer text, no claims, no claim statuses,
no citations, no GK labels, no register, no tool calls, and no figures.**

Two differences between the tiers, both small:

* the **CALENDAR ANCHOR** (`render_calendar`) reaches synthesis and not the parse,
  because the dispatch adds `document` to the context only on the synthesis branch
  (`interpreter.py:1197`);
* the **SCOPE NOTE** (`dropped_qualifier`) is synthesis-only for the same reason.

Captured `synthesis_context_keys` on every synthesis turn:
`['card', 'document', 'history', 'last_answered_subject', 'selection']`.

### 2.4 A6 — the verifier's inputs

**No turn-N claim can ever be verified against a turn N-1 record.** `_synthesis_
dispatch:1183` constructs `EvidenceToolbox(explainer)` **fresh per dispatch**, and
`Synthesizer.synthesize:283` hands that same box to `verify_draft`. The message
list in `Synthesizer.draft:204` is built from scratch each call. Nothing is cached
and nothing is carried. Every synthesis turn re-reads the board from zero.
**INFERENCE from code, corroborated by measurement**: P8 T1 and P1 T5 asked the
same teaching question in different conversations and made different tool calls
(4 vs 2 board reads).

### 2.5 A7 — the repeat detector

`bundle_repeat` (`:1080`). `repeat` requires, over the last **2** turns: same route
**and** `_same_question` (Jaccard ≥ 0.8 on content words) **and** `_same_subject`
(order, plus op_seq **only where the turn carries the key**). `deaf` requires a
matching **answer fingerprint** over the last 2 delivered rows for a question that
is NOT the same. A subject changing mid-conversation kills `repeat` and is
deliberately invisible to `deaf` (its docstring's reasoning: a changed subject
changes the answer text, hence the fingerprint).

Both riders are stamped **only on the matched-route branch** — `bundle_repeat` and
`remember_delivery` are called at `interpreter.py:1753-1756`, inside `dispatch`'s
tail. A synthesis answer, a CLARIFY, a tray answer, a rolling answer, a prove-it
and an outage card are **neither measured nor remembered** by this mechanism.

### 2.6 A8 — which floors read history

**None of them.** `_apply_mobility_floor` reads `parsed` + `params` + the
**selection**; `_apply_audience_floor` reads `parsed` + `params` only. R-FF1's
"routing is history-sensitive" is a statement about the **PARSE**, not about the
floors: the floors attach to whatever route the parse named, and the parse is what
history steers. In code terms the mechanism is exactly one line —
`question_parser.render_context:186-190`, the RECENT TURNS block — plus
`_bind_from_context:289`.

### 2.7 A9 — the question ledger

**Write-only at answer time.** `QuestionLedger` is constructed in exactly two
places: `app.py:2010` (the write on every ask) and `app.py:1020` (the DEV-gated
`/ledger/refusals` view). No answer path reads it. R-AI1's "intelligence accrues
only in reviewable artifacts" is intact and the artifact is genuinely offline.

Session semantics: a session **starts** when `createAskPanel` runs (page load) and
**never ends**. It is not observable to the planner — `sessionId` appears in no
rendered string anywhere in `src/cockpit/src/`.

### 2.8 A10 — schedule binding

`schedule_id` reaches `run_ask` as a parameter and reaches **`ParseMemory.key`**
(`interpreter.py:327`, field `"sched"`). It reaches **nothing else**.

**`ANSWER_MEMORY`, `SYNTHESIS_MEMORY` and `_DELIVERED` are keyed by `session_id`
ALONE.** This is the input to P4 and P4 lands on it.

### 2.9 A11 — teaching-relevant state

**NONE. This is the expected answer and it is the baseline (d.1) scopes against.**
Stated plainly and checked three ways: `answer_budget` holds no session store and
`licence_for(intent)` is a pure function of the current turn's intent; no
`ClaimKind.GENERAL_KNOWLEDGE` / `ClaimStatus.GENERAL_KNOWLEDGE` value is written
to any memory object; no "concepts already explained" store exists under any name.
Depth granted in turn N is **re-decided from scratch** in turn N+1, and a GK label
applied in turn N does not exist in turn N+1's world.

---

## 3. What reaches each tier, per turn

Answered in §2.3 with the verbatim payload. The artifacts carry the **full prompt
string for every one of the 74 turns** — `parse_prompt` and `synthesis_prompt`
fields in each `*-turns.json`. Nothing here is reconstructed: the parse prompt is
`QuestionParser.prompt_for(question, context)` called on the same context object
the parse received, and the synthesis prompt is built from the context dict
captured **at `synthesize`**, i.e. after the dispatch has added `document`.

Parse prompt size, demo board: **~34,700 bytes**, of which the conversation
context block is **under 500**.

---

## 4. The history-sensitivity map (P2 / P2b), quantified

### 4.1 With a board selection, position changes nothing — byte-identically

**P2** (`artifacts/p2-turns.json`). One question, *"why cant this be moved"*, with
`ORD-000128 op20` selected, asked three ways: cold as turn 1; as turn 3 after a
mobility exchange; as turn 3 after an unrelated exchange.

| arm | route | intent | conf | subject source | note | answer sha1 |
|---|---|---|---|---|---|---|
| cold | `why-here` | why-here | 0.92 | **selection** | "resolved against ORD-000128 (from board selection); and about op20 …; read as EARLIER …" | `8ed98f95853c` |
| after-mobility | `why-here` | why-here | 0.92 | selection | *identical string* | `8ed98f95853c` |
| after-unrelated | `why-here` | why-here | 0.92 | selection | *identical string* | `8ed98f95853c` |

**All three answers are BYTE-IDENTICAL (1,370 bytes).** Where a selection is live,
the ladder's second rung wins and history contributes exactly nothing.

### 4.2 With no selection, the same words give three different answers — and the
### resolution is UNDISCLOSED

**P2b** (`artifacts/p2b-turns.json`). *"why cant this be moved earlier"*, nothing
selected:

| arm | route | subject bound | `source` | resolution note |
|---|---|---|---|---|
| cold | **CLARIFY** | none | — | *(empty)* |
| after `"why is ORD-000073 op10 placed where it is"` | **what-would-change** | **ORD-000073, op_seq 10** | `utterance` | **(empty)** |
| after `"how many orders are late"` | **CLARIFY** | none | — | *(empty)* |

The middle arm is the specimen. Nothing on the ladder could bind: no card, no
selection, `last_answered_subject` `{}`, and the history turn's `order` field
`null`. The subject was recovered by **the parse model reading the RECENT TURNS
block**, which emitted `raw: "ORD-000073"` with `from_context: true`; `bind_
subjects:325`'s "the model flagged it as pointed but also gave usable words"
fallback then resolved it. **The op grain 10 came from inside the previous
question's TEXT** — it exists nowhere else in the payload.

**`source` is reported as `utterance`.** `_subject_note` and `_with_assumptions`
read `SubjectSource`, so a model-recovered subject is indistinguishable from one
the planner typed, and **the disclosure line is empty**. Compare §4.1, where the
ladder resolved and the note said so in full.

**This is R-LD2's rule meeting a resolver R-LD2 did not know about.** *"Every
resolution the ladder made is disclosed"* is true and is not the whole story: the
ladder is not the only resolver, and the other one is silent. Ledger row **D-02**,
severity **planner-visible wrong answer** (an answer about ORD-000073 to a planner
who typed no order and was told nothing).

### 4.3 P1 — the ladder was dead for six consecutive turns

**P1** (`artifacts/p1-turns.json`), a six-turn typed conversation with no board
clicks. `sent_last_answered` is `{}` on **6 of 6** turns; every `sent_history`
turn carries `order: null, machine: null, op_seq: null`. Card and selection empty
throughout. **All four rungs of the resolution ladder were empty on every turn of
this conversation**, and the conversation still worked — T4 *"what would have to
change"* bound `ORD-000128` correctly, from the model.

The reason `last_answered_subject` was empty after T3, a `why-here` answer about
ORD-000128: **`why_here` is not in `_ORDER_SUBJECT_TYPES`**. That set holds four
members — `demand`, `start_reason`, `contested_fact`, `order_attributes` — plus
`machine_idle` for machines, against the **33 distinct `subject_type` literals** in
`explainer.py`.
`why_here`, `counterfactual`, `lateness_cause`, `later_move`, `synthesis` and 23
others carry **nothing** forward. Ledger row **D-03**.

The `askHistory` `order`/`machine` fields are filled from `currentSelectionRefs()`
— **the live board selection at the time of the turn, not the subject the turn was
about** (`askpanel.js:271, 280`). So the ladder's HISTORY rung is fed exclusively
by past board clicks and is structurally dead in a typed conversation. Ledger row
**D-04**.

---

## 5. The cross-version finding (P4), stated plainly

**IT BLEEDS, AND THE BLEED IS PLANNER-VISIBLE.**

**P4** (`artifacts/p4-turns.json`). The gesture reproduced is `main.js::
onVersionChange` — what fires after an accepted edit, a boundary move or a publish:
rebind `scheduleId`, clear the board selection, **touch nothing else**. History,
`lastAnswered` and `sessionId` all survive by design (`askpanel.js:419`; only
`clearSelection` is called at `main.js:748`).

**Direction A → B** (`rolling-db5395dc-2ae` → `rolling-c362baa4-1b0`):

* T1 on board A: *"102 late order(s): Of the 280 orders known to this plan…"*,
  **102 records**.
* Rebind to board B — 40 orders, 26 scheduled, **zero late**.
* T2 on board B, *"show me the evidence for that"* → `prove-it`, **record_count
  102**, rendering:

  > That was my answer to "how many orders are late and what is the total
  > tardiness cost". It came from a contracted route, so it has no per-sentence
  > claims to pick apart — here is the whole record set it was assembled from
  > (102 record(s)):
  >
  > - lateness_minutes = 5297.0 min for ORD-000001  [record: 2aafb20c…]
  > - lateness_minutes = 10849.0 min for ORD-000002  [record: 06e09705…]
  > … *(100 more)*

  **Board A's 102 record ids, with board A's lateness figures, served to a planner
  looking at board B** — a board on which every one of those record ids is absent
  from the evidence index and on which no order is late at all. T3 repeats it.

**Direction B → A** reproduces the carry and exposes a second, separate defect:
board B's `late-orders` answer is real testimony with **zero** records, and the
prove-it on board A says

> My answer to "…" was **authored copy** — it states what this product can and
> can't do, not a fact read off a record — so there is nothing behind it to open.

which is false of a testimony answer. **This one is NOT cross-version.** The
control (`artifacts/zero-record-control.json`) asks the same pair on board B alone
and gets the identical sentence: a zero-record testimony answer is described as
capability copy on its own board. Ledger row **D-06**, single-turn defect.

**The mechanism, stated for (d.1):** `ANSWER_MEMORY.remember(session_id, …)` and
`.last(session_id)` — `interpreter.py:251, 263` — take **no schedule id**. Neither
does `SYNTHESIS_MEMORY` or `_DELIVERED`. `ParseMemory.key` **does** include
`"sched"`, so the parse cache is safe and the three answer-bearing stores are not.
Ledger row **D-05**, severity **planner-visible wrong answer**.

**Scoping honesty — two things this finding is NOT.** The schedule **picker** is
safe: it calls `jumpToVersion`, a full `location.assign` reload, which mints a new
`sessionId` and empties `askHistory`. And this session drove the Python seam, not
the browser: the reachability claim for `onVersionChange` is an **INFERENCE** from
`main.js:745-754` and `askpanel.js:419` (no reload, no history clear, no
`forget_deliveries`), not a browser observation. Listed in §12.3 as the highest-value
thing (d.1) should confirm first; it is not a ledger row, because this session did
not observe it.

---

## 6. The decay boundary (P6) and the stability set (P7)

### 6.1 Decay — the boundary is 4 turns, exactly, and the drop is silent

**P6** (`artifacts/p6-turns.json`). Twelve turns; T1 establishes ORD-000128 op20
with a selection, the selection is then cleared, ten unrelated turns follow, and
T12 asks *"and why couldn't that one start earlier"*.

Measured from each turn's captured `sent_history`:

| turn | history sent | T1 still in the payload | `last_answered` |
|---|---|---|---|
| T2–T5 | 1, 2, 3, 4 | **yes** | `{}` |
| T6–T12 | 4 | **no** | `{}` |

**T1 leaves the payload between T5 and T6** — the deterministic consequence of
`askHistory.slice(-4)`. `last_answered_subject` was empty from T2 onward (the
`why_here` gap, §4.3), so the only decaying channel was history.

T12 → **CLARIFY**, `subjects: [{raw: "that one", ref: null, source: "utterance",
pointed: true}]`, note **empty**, body *"I need one more detail to answer 'and why
couldn't that one start earlier'."*

**The drop is silent and its consequence is honest.** Nothing said "I had that a
few turns ago and no longer do"; the clarify is a truthful statement of the
present. Whether that counts as a defect is a design question, not a finding —
listed in §9 as **Q4**.

### 6.2 Stability — the boundary is the TIER boundary

**P7** (`artifacts/p7-runs.json`, plus `p7-run{1,2,3}-turns.json`). P1's six turns
re-run three times with identical inputs.

**Settings, stated:** demo board `rolling-db5395dc-2ae` (386 bars, contract 1.15);
parse **Haiku** at prompt **v18**, `temperature=0` where the model accepts it
(`llm_compat`); synthesis **Sonnet 5** at prompt **v8**; conversation cleared
(`forget_deliveries` + all four client channels) before each run; **3 repeats**,
18 turns. Nothing below is claimed beyond what 3 repeats support.

**STABLE across 3/3 runs, all six turns:** `route`, `intent`, `register`, `tier`,
`followup_of`, `resolution_note`, `subject_type`, `subject_name`. The parse prompt
string itself is byte-identical per turn across runs.

**BYTE-IDENTICAL rendered answers** on the four contracted turns:
T1 `late-orders`, T2 `CLARIFY`, T3 `why-here`, T4 `what-would-change`
(sha256 prefixes `fbfd9395…`, `48627e05…`, `a18a1e17…`, `2cf0fc7d…`, each 3/3).

**VARYING:** the two synthesis turns, on every axis measured — text sha256 3/3
distinct on both; lengths T5 `[1687, 2539, 2286]`, T6 `[1420, 1369, 1509]`; kept
claims T5 `[5, 5, 4]`; tool calls differ in both count and identity (T6 read
`calendars` twice in two runs and `machine_occupancy` in the third).

**So T4's cross-turn anaphora — the model-recovered `ORD-000128` of §4.2's class —
reproduced 3 of 3.** That is a stability observation about one probe at n=3, not a
determinism claim.

---

## 7. Teaching across turns (P8)

**P8** (`artifacts/p8-turns.json`). A teaching question and three natural
follow-ups.

| turn | question | intent | route | tier | licence |
|---|---|---|---|---|---|
| T1 | *how does a frozen zone normally work on a board like this* | `teaching` | **synthesis** | synthesis | **LONG** |
| T2 | *can you show me that on my board* | `drill-down` | **drill-down** | route | — |
| T3 | *why doesn't that apply to ORD-000128* | `frozen` | **frozen** | route | — |
| T4 | *so what should i do first* | `briefing` | **briefing** | route | — |

**THE TEACHING REGISTER SURVIVES EXACTLY ONE TURN.** Every natural follow-up left
the second tier. Turns 2–4 carry no claims, no claim classes, no GK labels, no
depth licence and no cuts/closer disclosure — there is nothing for those mechanisms
to act on, because a contracted route has no claims. Answering the brief's four
questions directly:

* **do GK labels persist and stay correct under R-TG1's two directions?** The
  question does not arise: turns 2–4 have no claims to label. Across turns the GK
  class does not exist. R-TG1's directions are per-answer predicates and there is
  no second answer to apply them to.
* **does the depth licence re-decide per turn or carry?** **Re-decides, from the
  intent alone.** T1 LONG; T2–T4 are not synthesis at all, so no licence is
  computed. `answer_budget.licence_for` reads nothing but `parsed.intent`.
* **does each turn re-read the board per R-TG5, or lean on turn 1's read?**
  **Cannot lean — structurally.** §2.4: a fresh toolbox per dispatch, no message
  carry. T1 made 4 tool calls (2 board reads); turns 2–4 made none, being
  contracted routes that read the snapshot directly.
* **does the cuts/closer disclosure repeat verbatim?** Not reachable: T1 had
  `deferred: 0` (the closer is correctly absent — R-TG3's own clause) and turns
  2–4 have no disclosure to repeat.

**T1 itself was a good teaching answer** and R-TG5 held: 3 kept claims — two
`general_knowledge` correctly carrying no provenance, one **`verified`** board
claim (*"ORD-000209 is placed on CUT-01 starting 2026-01-05 07:00, right at the
plan reference date…"*) citing 4 refs and `read_from: ['placements_in_window']`.

**T2 IS A PLANNER-VISIBLE WRONG ANSWER AND IT IS THE SHARPEST SPECIMEN IN THE
DOSSIER.** *"Can you show me that on my board"*, one turn after that answer,
returned in full:

```
  CUT-01 is in a workload too dense to schedule cleanly  [WARNING]
       Affected: CUT-01
[rendered by: template | register: testimony]
```

A gate data-quality finding. It has nothing to do with frozen zones, nothing to do
with ORD-000209, and nothing to do with anything the previous turn said.

**The cause is §2.1 item 7 and it is not subtle.** `Intent.DRILL_DOWN`'s declared
meaning (`contracts/parse.py:813`) is *"open the full record behind something the
assistant JUST said, when the question adds no subject of its own"*. Its assembler,
`_explain_drill_down` (`explainer.py:4136`), takes a `history` argument whose
docstring says *"Context-carried when the caller passes the prior turn's records"*
— **and no caller ever passes it**, because `route_params` never sets
`params["history"]`. With no ordinal in the question, the route falls to
`findings[0]`: **the board's most severe data-quality finding**, whatever the
conversation was about.

**`ANSWER_MEMORY` — the store 4B.22 built for exactly this gesture — is not read by
`drill-down`.** Its single reader is the `prove-it` branch. So *"show me the
evidence for that"* (→ `prove-it`) grounds the last answer, and *"can you show me
that on my board"* (→ `drill-down`) opens an unrelated gate warning. Two phrasings
of one gesture, two intents, one of them wired and one not. Ledger row **D-01**,
severity **planner-visible wrong answer**, multi-turn-specific.

T3 is the counter-example worth recording: *"why doesn't that apply to
ORD-000128"* correctly recovered *that* = the frozen zone from history, routed to
`frozen`, and answered well (*"ORD-000128 is placed, but after the frozen boundary
(2026-01-06) — it sits in the active part of this window…"*). **Cross-turn concept
reference works when a contracted route happens to cover the concept.**

T4 *"so what should i do first"* → the whole-board `briefing`, opening on *"The
cost optimum is NOT proved — the solver stopped with a gap of 89.6%"*. That is the
known R-TG4 opener finding (docs/07 §5a.169) arriving in a teaching conversation,
where it is further off-topic. Recorded as brushing an existing item, **not
pursued**.

---

## 8. Harness / product parity (Part C)

`src/mre/ai_exam/runner.py` builds a conversation the way `askpanel.js` does, and
the module docstring says that is deliberate. Verified field by field. **Two
divergences, one of them material:**

1. **AN ERRORED TURN ENTERS THE HARNESS'S HISTORY AND NOT THE COCKPIT'S.**
   `runner.py:691` appends to `history` **unconditionally**; only the
   `last_answered` update at `:705` is guarded by `if error is None`. In
   `askpanel.js` the `askHistory.push` at `:272` sits inside the `try`, after
   `appendAnswer`, so a turn that threw (`appendTransportError`) is **never
   recorded**. So the harness can present a failed turn to the next turn's parse
   and the product cannot. Ledger row **D-08**.
2. `resolved_subject` (`runner.py:303`) and `resolvedSubject` (`askpanel.js:59`)
   hold **identical** type sets and identical placeholder handling (`""`, `"?"`,
   `"all"` → `{}`). No divergence. The `op_seq` key is present-and-null in both,
   which is what `_same_subject` distinguishes from absent.

Everything else matches: 4-turn slice, the same five context keys, one stable
session id per conversation, RESET clearing all four client channels plus
`forget_deliveries`.

**What the sweeps have therefore NOT been grading.** Every committed bank is a
sequence of turns with **RESET between blocks and no cross-board rebind**, and
every expectation in `RUBRIC.md` C1–C9 is scored **per turn**. So the banks grade
single-turn correctness in the presence of history; they do not grade, and have
never graded, (a) whether turn N+1 uses turn N's content, (b) what happens when the
board changes under a conversation, or (c) whether a register survives a follow-up.
**A sweep CAN grade (d.1)** — the harness carries the right channels and RESET
works — **but only after per-turn expectations gain a way to reference an earlier
turn**, which no bank format has today. That is a (d.1) scoping input, not a fix,
and **the harness was not changed.**

---

## 9. The defect ledger and the design questions (Part D)

### 9.1 Ledger

| id | defect | probe / artifact | severity | multi-turn? | owner |
|---|---|---|---|---|---|
| **D-01** | `drill-down`'s declared meaning promises the previous answer; its assembler never receives it (`params["history"]` is never set) and falls through to the board's most severe gate finding. `ANSWER_MEMORY` is read only by `prove-it`. | P8 T2, `p8-turns.json` | **planner-visible wrong answer** | **yes** — needs a turn N to be wrong about | **R1** |
| **D-02** | A subject recovered by the PARSE MODEL from the history block reports `source: utterance` and is **disclosed nowhere**; the same subject recovered by the ladder is disclosed in full. | P2b after-mobility vs P2, `p2b-turns.json` / `p2-turns.json` | **planner-visible wrong answer** | **yes** | **R1** |
| **D-03** | `last_answered_subject` covers **5 of the 33** `subject_type` literals in `explainer.py`. `why_here`, `counterfactual`, `lateness_cause`, `later_move`, `synthesis` and 23 others carry no subject forward, so the rung built to carry a TYPED subject is empty after most answers. | P1 (6/6 turns `{}`), P5, P6; `p1-turns.json` | **silent state loss** | **yes** | **R1** |
| **D-04** | `askHistory`'s `order`/`machine`/`op_seq` are filled from the live **board selection**, not from the turn's own subject, so the ladder's HISTORY rung is structurally dead in a typed conversation. | P1 (all `null`), `p1-turns.json` | **silent state loss** | **yes** | **R1** |
| **D-05** | `ANSWER_MEMORY` / `SYNTHESIS_MEMORY` / `_DELIVERED` are keyed by `session_id` **alone**. After an in-place version rebind, a drill-down serves the OLD board's records against the new board. 102 record ids, verbatim. | P4 A→B, `p4-turns.json` | **planner-visible wrong answer** | **yes** | **R1** (store keys) + **R2** (does the rebind clear?) |
| **D-06** | A zero-record TESTIMONY answer is described by `prove-it` as *"authored copy — it states what this product can and can't do"*. | P4 B→A + `zero-record-control.json` | planner-visible wrong answer | **no** — single-turn, multi-turn merely surfaced it | **R1** |
| **D-07** | `deaf` fires on a legitimate deictic follow-up that correctly re-resolves to the same subject and correctly gets the same answer, telling the planner *"I'm not understanding what you're asking"*. The parse reports `followup_of: deepen` on that very turn and the rider does not read it. | `deaf-control.json` T2 (2 turns, cold) | planner-visible wrong answer | **yes** | **R1** |
| **D-08** | Harness/product divergence: `runner.py:691` records an ERRORED turn in history; `askpanel.js:272` does not. | Part C, code | cosmetic (measurement fidelity) | **yes** | **R1** |
| **D-09** | The OUTAGE turn enters client history and reaches BOTH tiers' payloads as `-> answered with intent: OUTAGE` — a token outside the closed intent vocabulary the prompt renders. **R-OF1's ANSWER_MEMORY exclusion itself HELD** (P5 T4 grounded T3, not the outage). | P5, `p5-turns.json` (parse prompt captured) | cosmetic / unruled | **yes** | **R1** |
| **D-10** | `_repeat_depth` is dead on the product path — no `src/` caller, tests only. | code census §2.1 | cosmetic | no | **R1** |
| **D-11** | `_DELIVERED` has a per-session cap of 4 rows and **no cap on the number of sessions**; a long-lived process accumulates one entry per browser tab forever. `AnswerMemory`/`SynthesisMemory` are LRU-32; this one is not. | code, `interpreter.py:988` | cosmetic (unbounded growth) | no | **R1** |

**One TRUE POSITIVE, recorded because the record says there have never been any.**
P6 T7: `deaf` fired on *"what does the certificate say"* after *"are there any data
quality problems"* — and it was **right**. Both bodies are the identical *"4
data-quality problem(s): …"* list (sha1 of T4's body `d7d7f05f6e0e`; T7's body is
T4's with the rider prepended). `certificate-testimony` and `data-problems` render
the same answer, so **the certificate route does not state the certificate**.
docs/07 §5a.42 records four `deaf` firings with zero true positives and §5a.58
records two more with zero; this is the first. The route defect is a
**single-turn** finding that only a multi-turn rider could have surfaced. Routed to
**R1**, filed as part of D-07's family but distinct from it.

**Items a probe brushed and did NOT pursue,** per §7 of the brief: the `briefing`
opener's top-ranked worry (P8 T4 — §5a.169, on the record); the gate's *"workload
too dense"* phrasing (R2 queue item 2); `_sample_note`; `_open_windows`' fortnight
pad. One line each, no design.

### 9.2 The design questions the room must settle before (d.1) can be scoped

Named, not answered. The brief listed five candidates; measurement confirmed four,
refuted the framing of one, and added two.

* **Q1 — May conversation state ever GROUND a claim?** **CONFIRMED as open.**
  Today the answer is a hard no and it is enforced by construction (§2.4): fresh
  toolbox, fresh message list, every turn re-reads. R-AI1 points that way; the
  latency argument points the other (a teaching follow-up currently pays a full
  synthesis to re-read what it read 8 seconds ago). D-01 shows the cost of the
  no: the drill-down cannot open what it just said because nothing is kept in a
  form a route can read.
* **Q2 — What happens to carried state when the board changes underneath it?**
  **CONFIRMED, and it is now a defect rather than a question** (D-05). What
  remains genuinely open is the RULE: does a rebind clear the conversation, does
  the store key on schedule id and refuse a cross-board read, or does the answer
  say *"that was the previous version"*? Three different products.
* **Q3 — Does depth granted in turn N persist into turn N+1?** **The framing is
  REFUTED by measurement.** Depth cannot persist because **the TIER does not
  persist** (§7): every natural follow-up to a teaching answer left synthesis
  entirely. The real question is prior to depth — *what makes turn N+1 of a
  teaching conversation a teaching turn?* — and it is a routing question, which
  is R-AI5 territory and the place R-TG2 deliberately refused to go.
* **Q4 — Does a GK claim labelled in turn N need re-labelling in turn N+1?**
  **Does not arise today** and the reason matters: turn N+1 has no claims at all
  (§7). It becomes live only if Q3 is answered such that a teaching conversation
  stays in the second tier.
* **Q5 — What can the planner SEE of the state that steers their answers?**
  **CONFIRMED as open and it is the sharpest one.** From the state map: the
  selection is visible (a chip), the card is visible, and **history, session id,
  `last_answered_subject`, `ANSWER_MEMORY`, `_DELIVERED` and the parse's own
  cross-turn resolution are all invisible.** D-02 is this question with a
  measured answer attached.
* **Q6 — NEW. Is a turn boundary a REGISTER boundary?** Measured: a conversation
  crosses `testimony → synthesis → system → testimony` freely and nothing
  reconciles the registers across turns. R-AI3's ladder governs one answer.
* **Q7 — NEW. What is the unit a bank grades?** §8: every expectation is
  per-turn and no format can reference an earlier turn. (d.1) cannot be graded by
  sweep until this is settled, and settling it is a harness-format decision, not
  a product one.

**Routed elsewhere, one line each:** **R2** — whether an in-place version rebind
should clear the ask panel (D-05's client half). **R4** — nothing found; no probe
touched the solver. **R3 / R5** — nothing found.

---

## 10. What a summary of this session would undersell

**That the resolution ladder is not what resolves follow-ups.** Six sessions of
comments, a docs/04 amendment and four named rungs describe a deterministic
mechanism that was **empty on all four rungs for all six turns of P1** — and the
conversation worked anyway, because the Haiku parse reads the RECENT TURNS block
and recovers the subject itself. A summary would report "history is carried" and
"the ladder resolves ellipsis" and both would be true sentences about a mechanism
that is doing far less work than its documentation implies. **The product's
cross-turn understanding is a model behaviour wearing deterministic clothes**, and
the clothes are why nothing discloses it (D-02).

**That the sharpest defect is a parameter nobody passes.** D-01 is not a design
gap. `_explain_drill_down` has a `history` argument, a docstring explaining what to
put in it, and no caller that does — since the day it was written. `ANSWER_MEMORY`,
built one session later for precisely this gesture, was wired to `prove-it` and not
to the intent whose declared meaning is *"open the full record behind something the
assistant JUST said"*. Two mechanisms for one gesture, neither aware of the other.
A summary saying "drill-down needs conversational grounding" would read as a
feature request; it is a wire that was never run.

**That P2 and P2b are the same probe and disagree completely.** With a selection,
three positions give **byte-identical** answers. Without one, the same words give
**CLARIFY / a full counterfactual about an order nobody named / CLARIFY**. Any
single number for "how history-sensitive is routing" is wrong; the sensitivity is
zero where a selection is live and total where one is not, and the boundary is
whether the planner happened to click a bar. **The founder listening round that
produced R-FF1 was conducted by someone clicking bars.**

**That the teaching graft's four sessions of work have a one-turn shelf life.**
R-TG1's claim classes, R-TG3's depth licence, R-TG5's read-the-board rule and C9's
transfer pairs all govern **turn one**. Measured on the four most natural
follow-ups a planner could type, **zero** stayed in the tier those rulings govern.
Nothing is broken — each ruling does what it says — but a planner who asks a
teaching question and then asks anything else is out of the teaching product
immediately, and (d.1)'s subject is therefore not "multi-turn teaching depth" but
"what makes a second turn a teaching turn at all".

**That two things this session expected to find are NOT defects, and one rider
earned its keep.** `repeat` is correct on all four P3 cases including the two the
4A.y fix was built for (different subject, different grain). R-OF1's rider holds
live: the outage card stayed out of `ANSWER_MEMORY` and the drill-down two turns
later opened the last REAL answer. And `deaf` — which the record says has fired
six times across two sessions with zero true positives — produced its **first true
positive** here, and what it caught is that `certificate-testimony` and
`data-problems` render the same body. The rider found a route defect nobody was
looking for.

---

## 11. Acceptance

1. **Stale-process check stated and passed before any live number** — §1. No
   serving process existed; every measurement is in-process at HEAD `e10376b`.
2. **Every claim carries its probe id and artifact path**; the four inferences are
   labelled **INFERENCE** (§2.2, §2.4, §5 scoping, D-11's reachability).
3. **No product source changed.** All spike code is under
   `tools/spikes/multiturn_recon/`. **No temporary edit was made to any file under
   `src/`**, so there is no restore to prove. The outage seam (P5) was driven with
   a **transport double** (`UnreachableClient`) injected through
   `QuestionParser(_client=…)`, a constructor parameter the shipped code already
   exposes for tests — the product code path is the shipped one.
   **One instrument bug is recorded rather than hidden:** the harness's first
   version read `record_ids` (the DRAFT field) off a `VerifiedClaim`, which
   silently yields `[]`. P8 was re-run after the fix and **the corrected reading
   changed this dossier's account of D-01** — the first run's "the drill-down
   opened a record the answer cited" was wrong; it opens the board's worst gate
   finding regardless. The fix and its reason are commented at
   `conv.py`'s claim capture.
4. **Suites** — see §12.
5. **Minted children: NONE.** No schedule, no run, no snapshot, no registry row.
   Two artifacts WERE written into the demo board's existing sandbox directory and
   are named rather than glossed: `_data/runs/db5395dc-…/sandbox/runs/{4917959f-…,
   871018b7-…}.jsonl`, two M5 `local_price` RunContext sidecars minted by the
   mobility route's later-direction pricing during P2. They are evidence sidecars
   in a directory that already holds ~150 of them. **Also named: a stray empty
   `registry.sqlite` scaffold** was created inside that sandbox directory by a
   `Registry(Path("_data"))` call made from the wrong working directory during
   analysis; it contained six empty tables, and it was inspected and **removed**.
   Nothing else under `_data` was written (`find _data -newermt "-4 hours"`).
6. **Corpus index NOT rebuilt, and it is correct not to be:** `corpus.py:146`
   explicitly **excludes** `docs/closeouts/*.md` from the index. **No docs/04
   amendment** — recon rules nothing.
7. Commit + push; this close-out is a file at the path above.
8. **What could not be measured, named** — §12.3.

---

## 12. Counts, and what was not measured

### 12.1 The measurement

**74 captured turns** across 10 probes and 2 controls, all live (parse Haiku v18 +
synthesis Sonnet 5 v8), all read-only against the two pinned boards, ~3.6 MB of
payload artifacts. Both pinned boards untouched and still resolving.

### 12.2 Suites

Baseline for this tree, from the session-(c2) close-out: **2658 passed / 305
skipped / 0 failed**.

**After, measured this session: `python -m pytest -q` → 2658 passed, 305 skipped,
12 warnings, 0 failed, in 1453.50s.**

**UNCHANGED, and it has to be** — this session added no test and touched no file
under `src/` or `tests/`. The delta is zero and there is nothing to explain.

`--runslow` NOT run and the cockpit suite NOT run — §12.3.

### 12.3 What could not be measured, and why

* **Part A / P4's browser half.** No probe drove Chrome. The claim that
  `onVersionChange` reaches D-05 in the shipped cockpit is an **INFERENCE** from
  `main.js:745-754` (it calls `setScheduleId` and `clearSelection` and nothing
  else) and `askpanel.js:419` (`setScheduleId` mutates one variable). The Python
  seam is measured; the gesture that reaches it is not. **This is the single
  highest-value thing (d.1) should confirm before scoping D-05.**
* **P6's decay boundary was read off the captured payloads, not bisected.** The
  boundary is `slice(-4)` and the twelve turns confirm it, but no probe varied the
  window size — nothing here proves the model would still resolve at 5 or 6.
* **The `deaf` false positive (D-07) has n=2** — P5 T3 and its control. The
  control proves it is not outage-caused; it does not establish a rate.
* **P8's teaching-follow-up routing has n=1 per phrasing.** Four follow-ups, one
  run each. The synthesis tier varies run to run (§6.2), so a second run could
  route differently; the four turns are specimens, not a rate.
* **The parse's cross-turn resolution (D-02) was measured on two probes** (P1 T4,
  P2b after-mobility) and reproduced 3/3 in P7 for P1 T4 only. No sweep-scale
  count of how often the model resolves where the ladder cannot exists, and
  producing one is a (d.1) instrument question.
* **`--runslow` was not run.** No `src/` change was made, so there is nothing this
  session could have broken there, and (c)'s known red (`test_ai_voice.py::
  test_cu5_split_jobs`) is not claimed either way.
* **The cockpit suite was not run.** No cockpit file was touched.
