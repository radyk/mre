SESSION 4A.3-pre CLOSE-OUT
R-AI3 (the register ladder): restore judgment, add invitation, fix the
round-two exam findings
2026-07-24

Deterministic settings for all solver work: PYTHONHASHSEED=0, --solver-workers 1,
--solver-seed 42/0.

======================================================================
SUMMARY
======================================================================
The founder's round-two listening session (2026-07-24) ran four failures against
the 4B.4 voice. R-AI3 was ruled (the register ladder: every answer starts with the
facts) and transcribed verbatim to docs/04. This session implemented it.

Backend-only: explainer + renderers + interpreter + authored ask copy + a NEW
authored capability registry + the audit corpus + docs. No solver/model/contract/
frontend changes. NO golden moved (none of the changed source files touches a solve
path, and the full non-slow suite is green including the solver golden guards).

Result: non-slow Python 1249 passed, 0 failed (+6 fast). Slow test_ai_voice 78
passed (+15 R-AI3 specimens; 4 folded into the zero-confident-wrong aggregate).
test_glass_box + test_ask_chain_api 34 passed.

======================================================================
PER-CU: CLAIMED vs PROVEN
======================================================================

CU1 - restore judgment + the regression guard
  CLAIMED: find where "My take:" detached; restore it through the pre-computed-
    facts pattern so the LLM cannot paraphrase it away; extend takes to routes
    where evidence grounds them; negative test for lookups; flagship regression
    guard; advice route ends with grounded judgment.
  PROVEN:
    - Archaeology (one line, from docs/04, not a guess): the take rode the
      TEMPLATE floor ONLY - authored there in 4A.2d and NAMED as debt in 4A.2d's
      own close-out ("the LLM testimony path renders facts under its strict
      no-opinion rules, so the 'My take:' offer currently rides the TEMPLATE
      floor"). The DEV/live LLM build showed the take merely inside the EVIDENCE
      CHAIN (not the pre-computed facts) and its 2-3-sentence no-opinion prompt
      paraphrased it away. Never a code regression; a detachment the LLM default
      made visible.
    - FIX: renderers._append_take appends the AUTHORED take after the LLM
      testimony on the success path, so a model that omits it cannot drop it.
      Proven by a standing LLM-path test (injected client returns testimony
      WITHOUT the take -> the render still contains "My take:").
    - Takes on why-late (flagship) and the advice route (which now ENDS with a
      grounded take naming the worst slip's biggest lever). Lookups carry none -
      a negative test (machine-count / inventory / product) asserts no "My take:".
  UNDERDELIVERED (named): the why-on-machine "priced alternative" take was
    DELIBERATELY NOT added. The EARLINESS_PREFERENCE hedge already provides a
    labeled epistemic judgment on why-on-machine, and a cost-take there needs the
    forced-alternatives price payload and would risk an UNGROUNDED opinion, which
    R-AI3(2) forbids ("may never be ungrounded"). why-late + advice deliver the
    causal + aggregate/diagnostic takes; why-on-machine-priced is deferred.

CU2 - invitations (minimal honest slice)
  CLAIMED: one authored invitation per route with an obvious follow-up, phrased as
    a question proposing a SUPPORTED route; frequency discipline; presence + absence
    tests.
  PROVEN: INVITE_LATE_ORDERS / INVITE_WHY_LATE / INVITE_DATA_PROBLEMS in
    ask_fallback_copy (authored). late-orders -> "Want the cause chain for the worst
    one? Ask 'why is ORD-05 late?'"; why-late -> "Want to see what else queues behind
    CUT-01?"; data-problems (>1 problem) -> "Want the fix-first ordering?". Tests:
    presence on the three routes, ABSENCE on lookups. The register ladder stacks
    testimony -> take -> invitation on the why-late answer.

CU3 - start-reason polarity
  CLAIMED: "why so early / not due until {date}" -> earliness floor answer + lower
    bound; "why late / not sooner" keeps the lower-bound chain; corpus specimens.
  PROVEN: _is_why_early detects the adjective / due-vs-start / already-started cue
    and EXCLUDES the comparative "earlier"/"sooner". A why-early answers the R-SC3
    floor in plain words (finishing early is free; cost-equal work placed as early
    as it can, banking slack) + the concrete lower bound as supporting testimony +
    the EARLINESS_PREFERENCE note when a declared coefficient moved it. Specimens:
    ORD-13 why-early gets the floor; ORD-05 "start sooner" keeps the lower bound.

CU4 - coaching/capability shape (retrieval, not training)
  CLAIMED: new taxonomy shape retrieving from EXISTING authored corpora + a
    section citation, jurisdiction rule intact; anchor splittable/min_chunk cites
    docs/06 5.3; extend the structured registry for anchor cases and NAME
    prose-locked scope as debt; fix "No calendar closures found for all resources".
  PROVEN: a NEW authored structured registry, src/mre/modules/capabilities.py -
    frozen dict[concept -> CapabilityNote] carrying authored enables/how + a docs/06
    section citation borrowed verbatim from the gate's RULE_REGISTRY ids_ref
    strings. The `coaching` route retrieves it; anchor "i want orders to span
    downtime, how" -> splittable=true + min_chunk_minutes on the routing line,
    5.3. Seven concepts seeded. Jurisdiction rule intact (coach the IDS field + its
    section, never ERP surgery). Grammar fixed: "No downtime is declared for any
    resource." + that question now reaches coaching. NAMED DEBT: docs/05 is PROSE
    with no structured backing (confirmed by an Explore pass), so the fuller
    constraint-coaching surface ("why can't it do X") is prose-locked and NOT built;
    retrieval is never taught to read prose.
  NOTE: the recommendation was to author a NEW registry (RULE_REGISTRY and the
    remediation catalog are both FINDINGS-keyed and need a certificate finding as
    input, which a coaching question does not have). Followed.

CU5 - the hypothesis-content guard
  CLAIMED: intervention STATEMENTS route to advice/coaching by content shape, never
    a status recital; corpus specimen.
  PROVEN: _is_hypothesis (a conditional/speculative marker + a plant/outcome word).
    A hypothesis naming a config concept -> coaching; one without -> advice. The
    founder's "maybe if splitting were allowed fewer orders would be late" ->
    coaching (splittable). "overtime would probably help" -> advice. Deliberately
    NOT bare "would fix/help": caught and pinned a regression ("and what would fix
    it?" is an ellipsis follow-up, not a hypothesis) - three interpreter tests
    initially failed and were fixed by tightening the markers.

CU6 - the sycophancy guard (R-AI3(4))
  CLAIMED: a contested cited fact -> restate evidence warmly + offer to walk the
    chain; capitulation and hardening both FAIL; >=2 specimens (one contested-wrong,
    one contested-RIGHT that yields).
  PROVEN: the `contested-fact` route (contest marker + status word + order ref).
    Warm restatement over a pinned fact, LLM short-circuited so it cannot be
    softened. contested-WRONG ("isn't ORD-05 on time?") holds warmly, offers the
    chain, no capitulation. contested-RIGHT: an accurate correction ("no i meant
    ORD-04") yields via the existing correction-rebind and re-answers for the
    corrected referent.

CU7a - verify the ORD-000019 -> ORD-000015 blocked-by claim
  CLAIMED: verify against the current golden's world; TRUE -> confirmation; FALSE ->
    fabrication specimen, grade severe, STOP short of fixing blocked-by; report.
  PROVEN: VERDICT FALSE (fabrication). Mechanically verified against a deterministic
    busy_board re-solve (the only world matching F001-RES002 / ORD-0000xx naming;
    workers 1, seed 42, PYTHONHASHSEED=0; two solves byte-identical on the relevant
    rows). The shared-machine KERNEL is real (both orders' op10 land on F001-RES002)
    but the adjacency + 14:23 timestamp are stitched from unrelated facts:
    ORD-000019 op10 ends 2026-01-05 18:25 (not 2026-01-06 14:23) and ORD-000015 op10
    begins 2026-01-09 15:07 (~4 days later, ten orders between them); the only op
    anywhere ending at exactly 2026-01-06 14:23 is ORD-000039 op30 on F001-RES006 (a
    different order on a different machine). Filed severe in docs/04. blocked-by NOT
    touched this session. Note: the deterministic _blocked_by reads immediate
    same-machine occupancy and could not have produced a cross-machine timestamp,
    which points to the transcript's retelling rather than the mechanism; the
    founder's exact live board/seed is not recorded, so the origin is unresolved,
    not exonerated. A future audit should re-check with the recorded board.

CU7b - docs/04 debt entries (named, not built)
  PROVEN: two debts recorded in the docs/04 amendment - aggregate-cause coaching
    ("why so many late orders" -> the binding-constraint story) and the
    bare-elliptical "why so many" against the 4B.4 context slice.

======================================================================
DOCS + VERIFICATION
======================================================================
Same-commit: docs/04 (R-AI3 ruling verbatim + the Session 4A.3-pre amendment,
including the CU1 archaeology line, the CU4 prose-locked debt, and the CU7a
fabrication finding + CU7b debts), docs/07 v2.39, CLAUDE.md status block.

Non-slow Python: 1249 passed, 169 skipped, 0 failed (595s).
Slow test_ai_voice: 78 passed (+15 R-AI3 specimens).
Slow test_glass_box + test_ask_chain_api: 34 passed.
No golden moved.

Files changed:
  src/mre/modules/capabilities.py       (NEW - the authored capability registry)
  src/mre/modules/explainer.py          (coaching + contested-fact + hypothesis +
                                         start-reason polarity + advice take)
  src/mre/modules/renderers.py          (_append_take + coaching/contested renders +
                                         invitations + downtime grammar)
  src/mre/modules/interpreter.py        (coaching meaning in the interpreter prompt)
  src/mre/modules/ask_fallback_copy.py  (invitations + coaching offer)
  tests/test_ai_voice.py                (fast registry/polarity units + the R-AI3
                                         slow corpus + aggregate specimens)
  tests/test_explainer.py               (downtime grammar assertion updated)
  docs/04-design-history.md, docs/07-roadmap.md, CLAUDE.md, SESSION_CLOSEOUT.md
