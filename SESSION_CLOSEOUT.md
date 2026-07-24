SESSION 4A.3 CLOSE-OUT
The action bridge: the conversation reaches the board
2026-07-24

Deterministic settings for all solver work: PYTHONHASHSEED=0, --solver-workers 1,
--solver-seed 42/0.

======================================================================
SUMMARY
======================================================================
The founder's round-three listening session (2026-07-24, run pinned: solve #5)
proved the register ladder works where wired and found the remaining wall: the
conversation could DESCRIBE the board and never REACH it. This session builds the
bridge.

Backend (explainer + interpreter + renderers + capabilities + ask copy) + a small
cockpit tooltip + surfacing the already-sent selection channel. No solver/model/
contract/frontend-substrate change. NO golden moved (no changed source file touches
a solve path; the full non-slow suite is green including the solver golden guards).

Result: non-slow Python 1255 passed, 0 failed (+6 fast). Slow test_ai_voice green
with the new specimens (the whole file: 106 passed with --runslow). Cockpit planner
tooltip spec: 16 passed (light + dark). The full cockpit JS suite result is recorded
below.

======================================================================
PART 0 - CU7a RESOLVING AMENDMENT (docs/04, first)
======================================================================
CLAIMED: overturn the 4A.3-pre "fabrication" verdict on the ORD-000019 ->
  ORD-000015 blocked-by claim (confirmed TRUE on the live board, solve #5); record
  the standing protocol that audits run against the pinned run's persisted document.
PROVEN: docs/04 amendment written and appended FIRST, before the session amendment.
  The verdict is overturned with the mechanism named (CP-SAT non-reproducibility bit
  the AUDIT, which re-solved a different world); _blocked_by is exonerated and NOT
  modified this session (verified: no edit to _blocked_by). Standing protocol
  recorded.
UNDERDELIVERED: none.

======================================================================
PER-CU: CLAIMED vs PROVEN
======================================================================

CU1 - the swap/move bridge (the flagship)
  CLAIMED: a swap/move intent routes to a new route answering the R-AI3 ladder
    (testimony + take + bridge to the real board gesture); the panel proposes, the
    human drags; never a status recital.
  PROVEN: new swap-move route (classify _swap_move_kind + _find_order_refs;
    assembler _explain_swap_move + _swap_take_and_bridge; renderer _render_swap_move,
    header-only + authored-copy so the LLM renders it verbatim). Corpus specimen
    (slow, against the clean glass_box solve): "why not just swap ORD-04 and ORD-05"
    -> swap-move; names both orders + the 890-min lateness (testimony), "My take:"
    (grounded take), CUT-01 + "sandbox" (the gesture), asserts NOT a status recital
    and the honest "can't drag bars / you make the gesture" jurisdiction line. A move
    specimen ("move ORD-05 earlier") also bridges. Classify units (slow) pin the
    swap/move routing and that a bare "it" (no order) never becomes swap-move.
  UNDERDELIVERED: the cited_refs lit-bars highlight rides the existing channel (the
    orders' assignment Decisions are carried as ordered_records) but is not asserted
    by a cockpit test this session - it reuses the proven 3.1 CU4 mechanism.

CU2 - the absence-explaining pair (gap-between + machine-idle)
  CLAIMED: gap-between resolves the gap on the shared machine and names its cause
    (occupancy / closure / off-shift / upstream / else honestly unexplained, never
    vouched); machine-idle gives eligibility + where the work went.
  PROVEN: gap-between (_gap_cause + _closure_in_window + _machine_working_windows
    base-pattern fallback + off-shift detection) and machine-idle
    (_explain_machine_idle) built and rendered. Corpus specimens (slow): the
    ORD-09/ORD-02 gap names the UPSTREAM hand-off (ORD-02's cut step) on PAINT-01;
    the ORD-04/ORD-05 gap names OFF-SHIFT; machine-idle on a USED machine (CUT-01)
    says "isn't idle" + "carries" and asserts NO order name (never the wrong noun).
    Probed live against the real solve to confirm every branch fires correctly.
  UNDERDELIVERED: machine-idle on a GENUINELY-idle machine does not enumerate the
    ops that COULD run there (no eligible-set read on the monolithic path) - it
    scopes honestly and grounds in the manned-idle Metric where present. Named debt.

CU3 - selection context reaches the interpreter
  CLAIMED: the board selection reaches the interpreter; a demonstrative deictic binds
    SELECTION-FIRST, then recency, then clarify; the interpreted line shows the
    source; the founder's exact failure resolves.
  PROVEN: the /ask payload already carried the selection (verified in api.js /
    app.py); the fix is priority. _demonstrative_deictic + _typed_subject_with_source
    (selection-first, returns source) resolve BEFORE the router short-circuit. Fast
    units: selection beats history; falls back to history without selection; the
    definite article is excluded. Corpus (slow): ORD-13 SELECTED + ORD-05 in stale
    history + "whats the end time of this order" -> binds ORD-13, "board selection"
    in the resolution note, ORD-05 absent; "why is this order late" with a selection
    answers late-order for THAT order; with no referent it clarifies. Cockpit: the
    ask-panel "interpreted as" line shows "[from board selection]".
  UNDERDELIVERED: none. (Frontend needed no new payload - the selection was already
    sent; only the priority fix and the visible source were added.)

CU4 - coaching-registry fixes
  CLAIMED: (a) bare concept names / trivial variants match, with a reverse-guard that
    every menu concept resolves by its own name; (b) an overtime concept (a BUILT
    capability); (c) a coaching-menu follow-up routes to the concept, not entity
    binding; (d) deictic/selection before the bare-"late" branch.
  PROVEN: (a) coaching_concept matches the slug + coaching_intent (concept + verb);
    fast reverse-guard test: every CAPABILITIES concept resolves by "explain <slug>"
    and by its bare name. (b) overtime CapabilityNote, ids_ref 5.6, how cites
    cost_model; fast test + corpus ("can i use overtime to help" -> coaching, 5.6).
    (c) resolve_followup CU4c intercept: "what about wip" after a coaching menu ->
    coaching wip, asserts no order op-dump. (d) shared with CU3's pre-short-circuit
    resolution. Corpus: "please explain wip" -> coaching (5.13, wip_status).
  UNDERDELIVERED: an ordinal menu reply ("the second one") clarifies rather than
    mapping to a concept (the menu order is not a stable contract) - intended.
    Named side-effect: overtime becoming coachable moved one 4A.3-pre test (the
    "overtime would probably help" hypothesis) from advice to coaching - the CU5
    rule (a hypothesis naming a config concept coaches the knob). The test was
    updated to the improved routing. Not a golden.

CU5 - riders
  CLAIMED: (a) the board hover tooltip on job bars gains order id, op seq, start->end,
    and the lateness/slack figure; (b) docs/04 amendment + honest gap-naming.
  PROVEN: (a) jobFor now carries start/end (from chunks) + latenessMin; the hovercard
    job card renders a "When" span (start -> end) and a "Slack" figure (fmtSlack:
    min/h/d, late vs early). Planner spec asserts When / Slack / the -> span, both
    themes, green. The card already had order id + op seq + machine. (b) docs/04
    amendment written (Part 0 first, then the session amendment); the reader was
    extended (base-pattern working windows), not approximated.
  UNDERDELIVERED: tooltip content/format is not exposed as feel tokens (the existing
    card is not tokenized); it matches the existing card's plain style. Minor.

======================================================================
OUT OF SCOPE (named, not built)
======================================================================
- The panel executing gestures / minting edits (never; M10 has no write path).
- Pricing a hypothetical WITHOUT the human's gesture (the sandbox two-beat is the
  pricing path; the bridge points to it).
- Aggregate-cause coaching ("why so many late") beyond its existing debt entry.
- The full docs/05 structured-constraint surface (prose-locked; retrieval never
  reads prose).

======================================================================
VERIFICATION
======================================================================
Non-slow Python: 1255 passed, 185 skipped, 0 failed (11m43s; confirmed twice).
Slow test_ai_voice (--runslow, whole file): 106 passed.
Cockpit planner spec: 16 passed (light + dark).
Full cockpit JS suite: 175 passed, 1 failed under the full parallel run (planner
  CU4 due-marker, light theme) - re-run in ISOLATION both themes PASS (a
  screenshot-timing flake under parallel load, not a regression; same class as the
  known 3.1c 0-bars flake). No cockpit test asserts on a hovercard height, so the
  When/Slack rows cannot have caused it.
No golden moved. No solver/model/contract/frontend-substrate change.

======================================================================
FILES CHANGED
======================================================================
src/mre/modules/capabilities.py  - overtime concept; coaching_intent;
                                    coaching_concept slug matching
src/mre/modules/explainer.py      - swap-move / gap-between / machine-idle routes +
                                    assemblers + taxonomy + classify + helpers
src/mre/modules/interpreter.py    - demonstrative selection-first resolution; CU4c
                                    coaching-menu follow-up; prompt meanings
src/mre/modules/renderers.py      - swap_move / gap_between / machine_idle renderers;
                                    header-only + authored-copy sets
src/mre/modules/ask_fallback_copy.py - route offers for the new routes
src/cockpit/src/board.js          - jobFor carries span + lateness
src/cockpit/src/hovercards.js     - job card When/Slack; fmtSlack
src/cockpit/src/askpanel.js       - resolution line shows the selection source
tests/test_ai_voice.py            - fast units + slow corpus specimens; one 4A.3-pre
                                    test updated (overtime hypothesis now coaches)
tests/cockpit/planner.spec.mjs    - tooltip When/Slack/span assertions
docs/04-design-history.md         - CU7a resolving amendment + Session 4A.3 amendment
docs/07-roadmap.md                - v2.40
CLAUDE.md                         - roadmap-position block
