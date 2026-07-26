SESSION 4B.5 CLOSE-OUT
Round-five harvest: the card tells the truth about itself, and the R-F rulings land
2026-07-26

Repo: C:\dev\mre, branch master. Deterministic settings throughout.
docs/07 v2.47; docs/04 amendment same date; CLAUDE.md position updated.

======================================================================
SUMMARY -- claimed vs proven, per CU
======================================================================
  CU1  delta attribution      DELIVERED + proven live on the founder's own board
  CU2  the open delta card    DELIVERED
  CU3  vacuous-causal         DELIVERED (audit + path fix + structural floor)
  CU4  banner + picker        DELIVERED (a,c,d,e proven; b named as defence)
  CU5  conversational riders  DELIVERED (d found a real defect)
  CU6  R-F1/R-F2/R-F3 + queue DELIVERED (transcribed, not built)

Tests: Python 1582 passed / 208 skipped (full non-slow). Slow sandbox ladder
72 passed. Cockpit JS 215 passed (both themes). New: 5 Python modules
(test_delta_attribution 22, test_open_card 28, test_causal_vacuity 27,
test_conversational_riders 24) + attribution.spec.mjs (9) + 6 new Playwright
specs. New corpus bank: regression_founder_r5 (26 questions, 26 graded).
No goldens moved.

======================================================================
CU1 -- DELTA ATTRIBUTION (the trust item)
======================================================================
CLAIMED: beat two gains a baseline solve; the card splits, always.

PROVEN, and the proof is the founder's own number. Re-ran the exact double
gesture on the LIVE incumbent (schedule rolling-279dec02-411 in _data, the
board the founder was looking at): ORD-000038's MILL-01 step, pinned first at
Jan-8 08:30 and then at 07:00, deterministic, standing pins = the committed
frozen front, restricted to the active window.

  gesture A -- Jan-8 08:30      (7.4s wall: 1.45s solve + 1.38s baseline)
    outcome              verdict / OPTIMAL   feasible=True
    TOTAL                -11967.03
    window re-optimize   -11975.83
    your move            +8.80
    sums exactly         True
    affected orders      ORD-000011 (-9800.42, -24477 min)
                         ORD-000003 (-2175.42,  -5758 min)
                         ORD-000019 (    0.00, +10080 min)
                         ORD-000013 (    0.00,  +4321 min)
    moved-set            8 ops

  gesture B -- Jan-8 07:00      (1.5s wall: 1.28s solve + 0.0s baseline [cached])
    TOTAL                -11967.03
    window re-optimize   -11975.83
    your move            +8.80
    sums exactly         True
    ... identical affected set, 8 ops

READ THAT SECOND LINE. -11,975.83 is the founder's number, to the cent -- the
figure both cards showed and that looked like what their move had done. It is
the WINDOW RE-OPTIMIZATION. Their move cost +$8.80, twice, and the card now
says so in its own row instead of hiding it inside a five-figure headline.

The two gestures still agree, and that is correct: both placements cost the
same $8.80. What changed is that the card now says they agree ABOUT THE MOVE
rather than about the plan -- and $8.80 vs $8.80 is a statement a planner can
act on, where -$11,975.83 vs -$11,975.83 was not.

Screenshot-level description of the card (light theme, rolling board): under
the headline "-0.05% cost - $11,967.03" sits a recessed two-row block --
"window re-optimization  -$11,975.83" in muted type, then a hairline rule and
"your move  +$8.80" in full ink, semibold. Below it, unchanged: the placement
line, the lateness line, the affected-orders table, the driver, the
committed-safe note, and the details disclosure.

Also proven: the second gesture paid 0.0s for its attribution (the baseline is
cached per incumbent), the two parts sum exactly to the total on both, a
cross-machine pin shows a nonzero move part different from a trivial pin's, and
suppressing the baseline yields the unsplit total plus the authored "includes
window re-optimization" line -- never a silent fused number, never a half split.

======================================================================
CU2 -- THE OPEN DELTA CARD JOINS THE RESOLUTION LADDER
======================================================================
CLAIMED: card > selection > last answer > history > clarify; "this move" binds
to the card and is answered FROM it; dismissal clears the context.

PROVEN. `SubjectSource.CARD` sits at the top of the ladder; `open-card` joins
the closed vocabulary (parse prompt v8, a vocabulary-class change committed with
Intent / INTENT_MEANINGS / ROUTE_TAXONOMY / ROUTE_OFFERS / assembler / authored
copy). The route re-derives NOTHING -- every figure comes off the sandbox result
the card is showing -- and it runs ahead of the clarify branch, because asking
"which orders do you mean" about the card in front of the planner is exactly the
dead end the clarify guard exists to prevent and a card is not a resolved
subject, so that guard cannot see it.

The founder's exact failing exchange ("what orders are affected in this move",
previously misparsed as swap-intent) is the regression specimen, graded, in
test_open_card.py AND in regression_founder_r5. With NO card open the same words
are answered "there's no priced move open on the board right now" plus how to
get one back -- never a guess, never a stale card. A card open does not capture
questions naming a different intent: it is a channel, not a mode.

Wiring proven in the browser: the controller publishes the card's own content
when one lands and clears it on discard / accept / return-home / a fresh grab;
the published payload's figures are ASSERTED equal to what the card is showing.

NOT DONE (named): a `CARD` directive was added to the exam script + runner so a
bank can open one, but this session had no ANTHROPIC_API_KEY, so the r5 bank is
COMMITTED AND UNRUN. It is graded when the next sweep runs.

======================================================================
CU3 -- THE VACUOUS-CAUSAL TRIPWIRE + THE WHY-ON-MACHINE AUDIT
======================================================================
(a) THE AUDIT, answered as asked. Record bafa03f1-1213-4e9b-9989-cb2ab529bec8
    (pulled from _data/runs/279dec02-.../runs/b738acd7-...jsonl) is a REAL
    assignment Decision: module M7, driver CAPACITY_BLOCKED, basis
    reconstructed, subject a real operation. The clause "the machine was busy
    with other work" is DRIVER_PHRASING["CAPACITY_BLOCKED"] VERBATIM.

    VERDICT: NOT an LLM reword of authored copy. The verbatim path is intact
    and this is not a CU4-4A.5b breach. The ASSEMBLER emitted it, using the
    driver phrase as the whole causal clause -- and that phrase names no
    machine, no alternative and no quantity. On a why-on-MACHINE question it is
    worse than thin: the machine that was busy is one the order did not get.
    The testimony validator passed it and was RIGHT to -- every check it makes
    is about fabrication, and an unfalsifiable sentence fabricates nothing.

    FIXED AT THAT PATH: a CAPACITY_BLOCKED placement now reads its story out of
    the solved occupancy -- which machines were eligible (capability_eligible
    over the op's own requirements) and what ran on each while the step ran.
    Three facts, never collapsed: alternatives occupied (named, with what held
    them and until when); no eligible alternative at all (a CAPABILITY fact --
    no rearrangement would have changed it); alternatives but none shown blocked
    (say the occupancy does not attribute it, and refuse to name one).

(b) THE STRUCTURAL GUARD. Causal routes (why-on-machine, late-order,
    start-reason, gap-between) gain a vacuity check: an answer naming neither a
    driver phrase, nor a concrete entity beyond the question's own subjects, nor
    a quantity FAILS CLOSED to the template. Proven against hand-built vacuous
    renders and on the real LLM render path.

    Its own subtlest bug, found by its own tests: entity refs carry digits, so
    scanning the raw text let "ORD-000008 is on PAINT-02" count as stating a
    quantity -- the exact shape it exists to catch. The question's own subjects
    come out before the quantity scan.

    TWO LIMITS, asserted so they cannot be assumed away. (i) The founder's own
    sentence PASSES the tripwire, because it reaches for the driver vocabulary;
    it is fixed at (a), not here. A floor cannot also be a ceiling. (ii) A
    quantity is a DIGIT -- "two other jobs were ahead of it" states a real one
    and still fails closed, which is the safe direction for a floor.

(c) The exchange joins the corpus graded (regression_founder_r5 section B).

======================================================================
CU4 -- BANNER + PICKER REPAIRS
======================================================================
(a) STICKY DISMISSAL -- proven. sessionStorage, per offered id, per tab. The
    root cause was concrete: the 4.4 dismiss handler removed the element and
    remembered nothing, and the watch's idempotence guard asked whether the
    banner was IN THE DOM -- so a dismissed banner failed it on the next check
    and was rebuilt, every 30s and on every focus. Test fires checkFreshness,
    focus and visibilitychange after a dismissal; the banner stays gone.
(c) ONE OFFER PER NEWER ID -- proven. The guard is what the tab has OFFERED,
    not what is in the DOM; the test asserts the SAME ELEMENT survives three
    re-checks (never torn down and rebuilt), and that a genuinely newer id is
    offered once in its turn.
(d) THE CARET -- proven. A caret at rest inside the chip (aria-hidden), rotating
    when the picker is open. A dotted underline only announces itself to someone
    already looking.
(e) dev_cockpit.ps1 RESUMES BY DEFAULT; -Fresh mints. The dev loop stops
    manufacturing the "newer schedule" noise the product then has to handle.

(b) VIEWPORT PRESERVATION -- DELIVERED, and honestly labelled. What the founder
    saw is diagnosed: on a tab with no uncommitted state the check AUTO-FOLLOWS,
    which is a full page reload, which resets everything -- 4.4 CU2 working as
    designed, firing constantly because every dev restart minted something newer
    to follow. (e) removes the supply; (a)/(c) remove the second source (the
    30-second rebuild, which reflowed the board each time). What ships as (b) is
    DEFENCE: any DOM the watch inserts is wrapped and the board window restored
    if the reflow moved it.
    UNDERDELIVERED, NAMED: on the harness fixture the prepend does NOT move the
    window, so the Playwright test for (b) is a standing invariant and NOT a
    reproduction of the symptom. Verified by stubbing the restore and watching
    the test still pass. Said out loud because a green test that never could
    have failed is worth what it cost.

======================================================================
CU5 -- CONVERSATIONAL RIDERS
======================================================================
(a) An ADVICE turn naming a capability routes to that capability's coaching.
    The concept is the PARSE's (the advice meaning now says to carry it); the
    dispatch only reads whether one resolved. Proven: the push-back's answer is
    not the advice answer; an advice question naming no capability still routes
    to advice; an unresolvable capability word does not divert.
(b) A route re-fired within TWO turns varies its lead from an authored tuple
    indexed by depth. Proven that the body beneath is byte-identical
    (`again.endswith(fresh)`) -- the facts never vary, only the lead.
(c) A re-asked COUNT answers "13 -- want the list?" instead of reciting. Proven
    the answer really shortens, the offer is only made when a list exists behind
    it, and the rendered-by footer survives (delivery metadata is not
    conversation).
(d) A REAL DEFECT, found by the verification this rider asked for.
    VerifiedClaim.consulted_record_ids was toolbox.consulted -- the ANSWER-LEVEL
    set, identical on every claim -- and the surface printed its first three
    beside every interpretive sentence as that sentence's provenance.
    Answer-level provenance wearing per-claim clothes is worse than none: it
    looks like an attribution and cannot be wrong, so nobody checks it.
    FIXED: it is now the claim's own scope (its citations when it made any; the
    whole consulted set when it made none, which is the accurate label), plus a
    new per-claim `read_from` naming WHICH TOOL CALLS surfaced those records,
    derived from the toolbox's own per-call record sets. Proven that two claims
    in one answer carry different provenance. It rides on the question-ledger
    entry and renders on the prove-it turn ("Read from: cost_ledger,
    lateness_set.").

======================================================================
CU6 -- DOCS
======================================================================
docs/04: this session's amendment, with R-F1 / R-F2 / R-F3 transcribed VERBATIM
and the four NAMED-QUEUED features summarized (the pin register;
amend-submission, flagged pilot-relevant; the boundary-drag feature; the window
constraint). docs/07 v2.47 same-day, with the rulings entered in the open-rulings
queue as item 6. CLAUDE.md position, ask-path paragraph and carry-forwards
updated. RUBRIC.md gains three new OPEN precedent entries (10 the open card, 11
the vacuous causal answer, 12 the repeat riders) so round six grades them rather
than rediscovering them.

======================================================================
OUT OF SCOPE (named, not built)
======================================================================
* Any R-F feature. The rulings are recorded; the pin register, amend-submission,
  the boundary-drag gesture and the window constraint are designed and queued.
* The two-solve baseline extended to FORCED-ALTERNATIVES pricing. Same
  economics, separate audit. CARRIED AS DEBT.
* Rendering-model changes.

======================================================================
UNDERDELIVERED / NAMED, in full
======================================================================
1. The r5 corpus bank is COMMITTED AND UNRUN -- no ANTHROPIC_API_KEY in this
   session. Its 26 expectations are graded by the next sweep. The CARD directive
   it needs is built and unit-parsed (26 q / 26 expect / 6 card, no parse
   errors), and run_ai_exam_sweep points the bank at the pinned rolling run.
2. CU4(b)'s viewport test is a standing invariant, not a reproduction (above).
3. The vacuity tripwire would NOT have caught the founder's own sentence; the
   assembler fix is what catches it (above).
4. THE COMMITTED ROLLING COCKPIT FIXTURE NO LONGER REPRODUCES. Regenerating
   tests/cockpit/fixtures/rolling/ moves the whole document -- different
   placements, a different cost summary -- because it predates the 2026-07-26
   errand's determinism fixes. That is a goldens move this session was not
   authorized to make, so sandbox.json was patched ADDITIVELY with an
   attribution split (figures SYNTHESIZED, on the precedent the builder already
   uses for its FLAGGED and NO_VERDICT cards). Regenerating it is a named
   follow-up, and a regeneration replaces those figures with real ones.
5. A pre-existing under-wait was found and fixed in the harness, not papered
   over: cockpit.spec.mjs's zoom test slept a fixed 150ms against vis's ~500ms
   zoom animation. It was green in isolation and went red once this session's
   frontend shifted the timing under file load. Bisected to main.js, confirmed
   green on the pre-session frontend, and fixed by polling for the property
   ("zoom out widens it") instead of a sleep. This is a TEST fix; no product
   behaviour changed.

======================================================================
TEST TOTALS
======================================================================
Python  full non-slow          1582 passed, 208 skipped
Python  slow sandbox ladder      72 passed  (sandbox, two_beat, rolling_two_beat,
                                             delta_attribution, planner_edit)
Cockpit JS (light + dark)       215 passed
Corpus banks parse clean         8 banks, 0 parse errors
Goldens                          unchanged
