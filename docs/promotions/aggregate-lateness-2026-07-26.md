# Promotion dossier -- aggregate-lateness

    cluster_id : late-orders|no-subject|lateness_set
    generated  : 2026-07-26
    source     : _ai_exam_scratch/dossier_replay/ledger.jsonl
    tool       : tools/promotion_dossier.py (machine-produced)
    draft route: docs/promotions/drafts/aggregate-lateness_route_draft.py

## What this is, and what it is not

This is an APPLICATION, produced autonomously by the promotion loop
(R-AI5(7)). It argues that a recurring shape of synthesis residue is
worth contracting into a route, and it shows its working.

It promotes nothing. The tool that wrote it cannot reach dispatch:
no Intent, no INTENT_MEANING, no ROUTE_TAXONOMY entry, no parse-prompt
line. Promotion is a REVIEWED CHANGE made by a session that has been
given this document; the working thread's review is the signature.
Demotion, by contrast, is automatic (R-AI5(7)) -- see PROBATION below.

## The shape

- **Frequency**: 2 question(s) in this ledger (of 15 synthesis answers over 58 questions).
- **Intent adjacency**: late-orders
- **Subject kinds**: none
- **Leaned on**: lateness_set
- **Also read**: placements_for_order, cost_ledger, placements_for_machine, calendars
- **Claims**: 4 verified, 4 interpretive, 0 cut (**verified share 50%**)
- **Pareto weight**: 1.00 (frequency x verified share)

### Exemplars (every question in the cluster)

- "why so many late orders"
- "whats actually driving the lateness in this plan"

## The evidence-assembly pattern

Derived from the transcripts of the answers that produced at least one
VERIFIED claim -- the ones that demonstrated the evidence CARRIES this
shape. Argument values are reduced to their shape; the pattern is
"call it with an order", never "call it with ORD-05".

```
lateness_set()   x2
placements_for_order(order=<order>)   x2
cost_ledger()   x2
placements_for_machine(machine=<machine>)   x1
calendars(machine=<machine>)   x1
```

The tool surface is a thin wrapper over the SAME readers a contracted
route uses (Session 4A.5b CU1), so a promotion is not a
reimplementation: it is this evidence assembled deterministically
instead of agentically.

## What a contracted route would have to be able to say

### Verified in synthesis (a route must PROVE these)

- Only one order is late: ORD-05, by 890 minutes (nearly 15 hours).
- ORD-05 is scheduled on CUT-01 from 07:00 to 14:50 on 2026-01-06, finishing at 14:50 UTC, but its due date is 2026-01-05 at 23:59:59 UTC — already past by the time it runs.
- ORD-05 is the only late order, finishing 890 minutes (nearly 15 hours) past its due date of 2026-01-05 23:59:59Z.
- ORD-05 is scheduled on CUT-01 from 2026-01-06 07:00 to 14:50, which is the day after its due date.

### Interpretive in synthesis (a route may prove, or must keep labeled)

- The schedule is not 'so many' late orders — 14 of 15 orders are on time or early; the lateness problem is concentrated in one order.
- ORD-05's lateness is a scheduling placement issue: it was scheduled to start after its due date had already passed, incurring 370.83 in tardiness cost.
- CUT-01 is fully booked on 2026-01-05 from 07:00 to 18:50 with ORD-13, ORD-02, and ORD-04 scheduled back-to-back, leaving no capacity for ORD-05 until the next day.
- ORD-05 cannot fit on its due date because the machine it requires is already committed to three other orders that day, forcing it to slip to the following day and miss its deadline.

R-AI5(6) applies inside a promoted route as much as outside it. An
interpretive claim a route cannot prove does not become true by being
assembled deterministically -- it stays a labeled reading or it is
left out. A promotion that launders a take into testimony is worse
than no promotion.

## Harness validation

Replayed **2** historical question(s) of this
cluster under the candidate route `lateness-cause` against the pinned
world, diffed against the synthesis answers recorded in the ledger.

- route raised on: **0**
- contradicted a synthesis claim on: **0**
- strengthened provenance (route CITES what synthesis could only
  read) on: **2**

```
  why so many late orders
    records cited : 4
    agreed on     : late_count
    contradicted  : -
    strengthened  : yes
    shadow only   : ORD-05 is scheduled on CUT-01 from 07:00 to 14:50 on 2026-01-06, finishing at 14:50 UTC, but its due date is 2026-01-05 at 23:59:59 UTC — already past by the ti
  whats actually driving the lateness in this plan
    records cited : 4
    agreed on     : -
    contradicted  : -
    strengthened  : yes
    shadow only   : ORD-05 is the only late order, finishing 890 minutes (nearly 15 hours) past its due date of 2026-01-05 23:59:59Z.
    shadow only   : ORD-05 is scheduled on CUT-01 from 2026-01-06 07:00 to 14:50, which is the day after its due date.
```

**CLEAN.** The route agrees with every verified claim it
speaks to. That is a necessary condition for promotion, not a
sufficient one -- whether the shape SHOULD be contracted is a
judgment, and it is the reviewer's.

## The gate (R-AI5(7))

Promotion is a vocabulary-class change. A session acting on this
dossier must land ALL of the following in ONE reviewed commit, citing
this file as the authority:

1. `Intent.LATENESS_CAUSE` in
   `mre.contracts.parse` (add, never repurpose).
2. Its authored one-line meaning in `INTENT_MEANINGS`, written to
   SEPARATE it from its neighbours -- the adjacency above is exactly
   the set of intents it will be confused with.
3. A `ROUTE_TAXONOMY['lateness-cause']` entry with its params and
   canonical question, and a `ROUTE_OFFERS` line.
4. The assembler + its AUTHORED copy (a human's, never generated).
5. A `parse_prompt.md` version bump documenting the new id.
6. A `Promotion` entry in `mre.contracts.promotion.PROMOTIONS`
   citing this dossier by path, status `probation`.
7. The docs/04 amendment.

## Probation and demotion

On promotion the route runs SHADOWED (`mre.modules.shadow`): every
sweep asks this shape's questions under BOTH paths and diffs the
route's pre-computed facts against the synthesis tier's verified
claims. A contradiction on a shared quantity fires a loud sidecar
signal and DEMOTES the intent automatically -- it leaves
`model_selectable_intents()`, the parse can no longer name it, and
the shape returns to the second tier.

Promotion is never automatic. Demotion always is. That asymmetry is
the ruling, not an implementation detail.

