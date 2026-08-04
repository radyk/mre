# Micro-session 4A — the floor tells the truth about why it fell

**2026-08-03.** One item, one ruling. **R-OF1** is verbatim in
`docs/04-design-history.md` (2026-08-03); the roadmap entry is
`docs/07-roadmap.md` v2.87, §5a.159-161. Contract unchanged at **1.15**; parse
prompt unchanged at **v17**; no docs/06 doorway owed, and both questions are
answered on the record rather than left implied.

**No child was minted, no board was re-solved, both pinned worlds are
untouched.** (Standing clause, 4B.35.)

---

## 1. The specimen

The founder's key ran out of credit mid-session. Three questions were typed into
the cockpit — *"find order and highlight 126"*, *"why cant ORD-000126 op30 start
earlier"*, *"why cant this be moved"* — and all three came back as the same
card. Three screenshots on file in the design thread:

> "I couldn't answer that one: I don't have a tool that reaches it. Nothing I
> can read holds that, so I'd rather say so than guess.
> Here's what I can do that's closest: …"
> `[rendered by: synthesis — 0 tool call(s)]`

**Every clause is false in that failure mode.** The tools were there. The
evidence was there. The board, the schedule and every gesture were untouched.
What was missing was the language model, so the question was never READ — and
the product answered a question about ITS OWN REACH with a sentence about the
PLANT's evidence, in the honesty register, under a footer naming a tier that
never ran.

The two facts need two sentences because a planner acts on them differently.
*"I can't do that"* is a reason to stop asking; *"I can't think right now"* is a
reason to ask again in a minute. The founder read the card as grounds to abandon
the AI layer. That is the price of the confusion, and the reason this is a
ruling rather than a copy edit.

---

## 2. The census, which is item 1

Every LLM-dependent step in the ask path, traced at HEAD before anything was
changed. The exception class is the same in every row — `call_text` catches
`Exception` — which is itself the finding.

| # | path | where the failure lands | what rendered at HEAD |
|---|---|---|---|
| 1 | **parse call fails** (HTTP error, timeout, auth, credit) | `call_text` → `None` → two attempts → `parse-failed` clarify → dispatch's clarify branch → `_clarify_leads_nowhere` (True: the intent is `unmatched`) → the second tier → the synthesis loop against the same dead transport | **the capability card**, `[rendered by: synthesis — 0 tool call(s)]` — **the founder's specimen** |
| 2 | **synthesis call fails, parse OK** (a cached preflight parse, or an outage of the synthesis tier alone) | `draft` nudges a dead transport for `_MAX_STEPS`, 0 tool calls, no claims → `unanswerable` | **the same capability card** — the specimen by its second route |
| 3 | **no key / no client, parser constructed** | `parse` returns `None` → `run_ask`'s unsupported bridge | *"I can't answer this question yet: `<question>`"* + the supported-routes menu — a claim about the QUESTION, from a layer that never read it |
| 4 | **no parser passed at all** (the API's degraded re-run; every R-AI5(2) test) | the same bridge | unchanged — **a deliberate boundary**, see §6 |
| 5 | **synthesizer unavailable, parse OK** | `_unmatched_bridge` | already honest: the question WAS read, the offers are computed from that real parse, and the bridge claims no tool gap |
| 6 | **the LLM VOICE renderer fails** | `_render_fail_closed` | already honest: degrades to the deterministic template with a logged Event; the answer is the assembled one |
| 7 | **the preflight fails** | `_preflight`'s `except` | already honest: fails open to the `route` tier, no waiting state |

**Three of seven were rendering an infrastructure failure as a capability
statement. Three were already honest. One is a boundary.** Rows 1–3 are what
this ruling fixes.

**THE ROOT CAUSE IS ONE VALUE.** Every model failure arrived at the ask path as
`None`. So *"the model answered unusably"* and *"the model could not be
reached"* were the SAME fact by the time anything could render a sentence about
them, and the capability floor was the only floor there was. It is not that the
copy was careless; there was nothing in scope for it to be careful about.

---

## 3. What shipped

**The classification, at the call** (`llm_compat.call_text_outcome`).
`UNREACHABLE` when `messages.create` itself failed — network, auth, rate limit,
credit exhaustion, a 400, a timeout, and a missing client, which raises there
and is correctly an outage because there is nothing to reach. `NO_TEXT` when the
call succeeded and no usable text came out of it: the model WAS reached, that is
a quality failure, and it keeps every pre-existing behaviour including the
retry. **Nothing string-matches a provider's wording** — the test is whether the
call completed, a property of our own transport. `call_text` survives as a thin
wrapper for the one caller that genuinely cannot act on why (the voice
renderer).

**Three stages, deliberately not one card.**

| stage | what is true | what the card says |
|---|---|---|
| `parse` | the question was never read | *"I can't reach my language model right now, so I couldn't read your question at all. This is an outage on my side, not a limit of what I can answer."* |
| `synthesis` | the question WAS read; no contracted answer covered it; the reasoning tier could not be reached | *"I read your question, but no contracted answer covers it and I couldn't reach my language model to reason it out."* |
| `unconfigured` | no model is available on this deployment | *"I have no language model available on this deployment…"* — **and no retry line**, because there is nothing to wait for |

Every card carries *"The board, the schedule and everything you can click still
work — nothing about the plan depends on me being able to talk."* A single card
for all three states would have to say the weakest true thing about every one of
them, which is how a fix for one lie becomes a smaller one.

**No doors.** `SYNTHESIS_FLOOR_DOORS` — *"here's what I can do that's closest"* —
presupposes the question was understood well enough to find a neighbour for it.
On the parse path nothing read it. Offering alternatives here would be a second
capability claim inside the card built to stop making the first.

**No silent retry, no queue, no degraded guess.** The parse retries once on a
malformed emission; a transport that is down is not answered by asking it twice,
and counting an outage as a malformed emission files an infrastructure failure
as a quality one. Both loops break at the first unreachable call. R-AI5(2) is
untouched — there is still no keyword fallback to reach for.

**The footer names no tier that did not run, and no register that did not
speak.** `[rendered by: authored copy — the language model was unreachable |
register: system]`. `system` joins the register vocabulary (ADD, never
repurpose): `testimony` says assembled from this plan's evidence, `synthesis`
says reasoned from it and labelled claim by claim, `judgment` says this is our
advice. An outage card is none of the three. **The browser had already made this
call** — `askpanel.appendTransportError` renders a failed fetch in deliberately
register-less chrome, on the reasoning that the question never reached the
server, so there is nothing in any register to read. The outage card is that
card's server-side sibling and wears the same dashed clothes (`.msg.answer.system`).

**Beat one may not promise a read that cannot happen.** `tier_of` returned
`synthesis` for an unreachable parse — the clarify leads nowhere, the intent is
`unmatched` — so the panel would have shown *"Reading the evidence — I'm working
it out from the records"* and then a card saying nothing was read. It returns
`floor`, which is what makes the panel show no waiting state at all.

**Where the branches live.** The dispatch's outage branch is **before
everything**, ahead of the tray, the card and the clarify: there is no subject
to resolve, no card to read back and no intent to honour, because every branch
below reasons about a parse that does not exist. `MODEL_UNREACHABLE` is
deliberately absent from `_CLARIFY_COPY`, as `SET_REFERENCE` is — it never
reaches the clarify bundle, because it is not a question back.

---

## 4. What the live run found that the guards did not

Twenty-one tests were green. Then the first outage card served from the real
demo board came back like this:

> I can't reach my language model right now, so I couldn't read your question at
> all. …
>
> **I haven't addressed the time you named — what I said above is when it does
> start, not whether it could have started then.** Ask "why is it here?" and
> I'll give you the binding constraint…

**"What I said above" was a card whose entire content is that nothing was
read.** The predicate-coverage rider fired on the outage floor.

Every rider on the delivery seam is a qualification OF AN ANSWER — the gap rider
qualifies a money claim, the sufficiency rider a cause, the coverage rider what
an answer did and did not address. The outage floor has no answer to qualify, so
a rider firing there re-commits the defect the card exists to end, one paragraph
below the card. Withheld at **BOTH** render seams (`_no_riders`), because a
floor one path can skip is not a floor (4B.23's rule at another site), and
asserted two ways: the rider's own words are absent, and the card is **exactly
four non-empty lines** — the authored copy plus its footer, with nothing
appended by anything.

**Only a live question against a real board could produce it.** The guard
fixture's questions do not carry a temporal qualifier, so no rider had anything
to fire on. This is 4B.21 §5a.78's species from a third side: a test that
supplies its own arguments proves the assembler, not the path.

**One mechanism, not two.** `predicate_coverage.uncovered_topic` already
exempts `clarify` / `unknown-entity` / `near-miss` / `synthesis` by ROUTE, and
adding `OUTAGE` there would have been correct too. It was deliberately NOT
added: `_no_riders` covers all four riders rather than one, and a second
mechanism would mask a regression in the first — control G would go green
against a reverted gate.

---

## 5. Verification

**Python 2548 passed / 291 skipped / 0 failed** (family-floor baseline 2524;
**+24**). Of those, 23 are the new `tests/test_outage_floor.py`; **three
pre-existing assertions were UPDATED**, and each update IS the ruling rather
than an accommodation of it:

* `test_a_raising_client_never_escapes` → `…_and_names_the_outage`. It still
  never escapes; the reason is no longer `parse-failed`, which means a model
  ANSWERED and we could not make a parse of what it said.
* `test_every_clarify_reason_has_authored_words` → `…_that_asks_…`, parametrized
  over the reasons that ASK, with `MODEL_UNREACHABLE`'s own destination asserted
  separately. It is the one member of the set that is not a question back.
* `test_an_unavailable_parser_is_the_same_honest_answer` → `…_is_an_outage_not_a_
  capability_limit`. The other half — a caller that passed no parser at all —
  keeps the bridge in the test directly above it.

**Cockpit 365 passed / 2 failed of 367.** The two are the known deictic pair
(`cockpit.spec.mjs:111`), red at HEAD since 4B.23 §5a.95. No new flake; the
cockpit change is two lines of JS and one CSS rule.

**Seven negative controls, every one proven RED** against physically reverted
code, and **every restore byte-identical** (sha256 asserted before and after —
4A.y's harness lesson, and the harness reads and writes BYTES only, matching the
file's own line endings):

| | reverted | guard that went red |
|---|---|---|
| A | the dispatch's outage branch | the parse-outage card |
| B | the second tier's outage branch | the synthesis-outage card |
| C | the unconfigured branch in `run_ask` | the no-model card |
| D | the classification at the call (every failure becomes `NO_TEXT`) | the classification test |
| E | the footer that names no tier | the footer test |
| F | the parser's break-on-unreachable | the no-retry test |
| G | the rider gate | the live run's own find |

**Live on the demo board `rolling-db5395dc-2ae`, three ways**, driven through a
real browser against the real dev API:

1. **Unreachable key** (an invalid key, so the client builds and the call
   fails — the founder's shape): the outage card, `route=OUTAGE`,
   `register=system`, dashed register-less chrome, chip reading `SYSTEM`.
2. **Key restored, the same question**: answers normally —
   *"ORD-000126 op30 couldn't start before Thursday 2026-01-15 10:29: op20
   finishes at 2026-01-15 10:28"*, the full blocker ladder, `register:
   testimony`, one bar lit on FINISH-01.
3. **A genuinely out-of-scope question with the model up** (*"what colour
   should i paint the shop floor"*): **the capability card, unchanged, doors and
   all**, `[rendered by: synthesis (claude-sonnet-5) — 0 tool call(s) |
   register: synthesis]`.

The third is the control that matters. The capability floor is exactly what it
was — and it now means what it says.

**MINTED NOTHING.** Commit `595704d`, pushed.

---

## 6. Carry-forwards (REPORTED, deliberately NOT fixed)

**(a) THE NO-PARSER BRIDGE IS UNCHANGED, BY RULING.** Census row 4. A caller that
passes no parser still gets *"I can't answer this question yet: `<question>`"* —
the same class of sentence, one register quieter. It is the one row where an
infrastructure fact can still read as a capability one. It is left because that
caller made a deliberate choice (the API's degraded re-run, and every test
asserting R-AI5(2)'s no-keyword-fallback), and nothing at that seam can tell
whether an AI layer was ever meant to be present. Naming it is the honest half:
this is a boundary, not a completed sweep.

**(b) THE OUTAGE CARD IS REMEMBERED LIKE AN ANSWER.** `ANSWER_MEMORY` stores it
as any other turn, so a drill-down immediately after a synthesis-stage outage
grounds the outage card — honestly, since it cites nothing — rather than the
last real answer. Unreachable in a full outage, since the drill-down needs a
parse too. Not ruled either way.

**(c) THE ASK DOCK'S COLLAPSE BADGE RENDERS THE LITERAL WORD "null"** on a fresh
board. Seen in this session's own live screenshots. `main.js` guards the METHOD
where it means to guard the VALUE — `badge: () => (panel.turnCount ?
String(panel.turnCount()) : null)`, and `turnCount()` returns
`askHistory.length || null`, so `String(null)` is what paints. Pre-existing,
cockpit-only, one line (`const n = panel.turnCount?.(); return n ? String(n) :
null`). **Left alone because it is unrelated to this item, and a session that
quietly fixes adjacent things makes its own diff unreviewable.**

**(d) `sweep_mobility_v2`'s `dark-evidence=2` IS TWO PREMISE CORRECTIONS AND
NEITHER IS A FINDING.** The two are *"why is ORD-000126 op30 on CUT-01"*
(R-FF4's own specimen — op30 runs on FINISH-01) and *"why is ORD-000126 on
HEAT-02"* (4B.13's order-grain control). Both are `why-on-machine` answers that
CORRECT a false premise, and a correction cites nothing because there is no
decision record for a placement that does not exist; the order's real placements
ARE its evidence, rendered inline. 4B.17 recorded this exact shape ("`dark-evidence`
fires on a premise correction, 2 per run") and the count is again exactly 2. The
sidecar detector predates the premise machinery and cannot tell a correction
from a silent route. **No action owed; the detector's limit is the finding, and
it is already on the record.**

**(e) R1 ITEM 1 IS CLOSED — nothing of it remains open.** The listening docket
(4A.x), the family floor (4A.y) and the honest-outage message (here) were its
three parts. §5b's queue is updated; what remains under R1 is items 2 and 3 and
the standing 0-of-5 direction-parse finding, none of which belong to item 1.

---

## 7. What the summary would undersell

**The lie was cheap to make and expensive to read.** Nobody wrote a false
sentence. `call_text` returned `None` on failure — a reasonable, fail-closed
choice — and every layer above it did the honest thing with the only fact it
had. The falsehood was manufactured by the JOIN: an HTTP error became "no JSON",
which became "the parse could not commit", which became "unmatched", which
became "the second tier found nothing", which became "I don't have a tool that
reaches it". **Five correct steps producing one false claim, each step
defensible on its own** — which is why the fix had to be at the first step, and
why the guard for it asserts the CLASSIFICATION and not just the copy.

**The card that ships is shorter than the one it replaces.** The capability card
offers doors; the outage card refuses to. That refusal is the whole ruling in
one behaviour: everything a floor says beyond *"here is what went wrong"* is a
claim about the question, and on this path nobody read the question.
