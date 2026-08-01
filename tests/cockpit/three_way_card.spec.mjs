// Session 4B.24 — THE THREE-WAY CARD (R-T2 amendment), as pure reads.
//
// Theme-free, no rendering: the `logic` project. What is pinned here is the
// READING RULE. Three registers have to stay apart on one card — the MOVE's
// price, the SEARCH's opportunity, and a REFUSAL — and the whole ruling exists
// because two of them were fused into one number and one label.
//
// The arithmetic itself is proven server-side (tests/test_local_price.py).
import { test, expect } from "@playwright/test";
import {
  LOCAL_NOTE, UNSPLIT_NOTE, attributionRows, opportunityBlock, signedMoney,
} from "../../src/cockpit/src/drag/sandboxui.js";

const local = (over = {}) => ({
  outcome: "verdict", feasible: true, pricing_mode: "local",
  cost_delta_abs: 0.0, attribution: "local",
  reopt_delta_abs: 0.0, move_delta_abs: 0.0, ...over,
});

// ---------------------------------------------------------------------------
// CLAUSE (2) — a local price has ONE row
// ---------------------------------------------------------------------------

test("a LOCAL price draws one row, and it is the planner's own", () => {
  const rows = attributionRows(local());
  expect(rows.map((r) => r.key)).toEqual(["your move"]);
  expect(rows[0].own).toBe(true);
});

test("a local price NEVER draws a 'window re-optimization $0' row", () => {
  // The failure this guards is subtle and is the reason clause (2) is worded the
  // way it is: a zero row claims a MEASUREMENT. Nothing measured the window here
  // — nothing else was allowed to move, so there is no re-optimization component
  // to report, absent rather than zero.
  const rows = attributionRows(local());
  expect(rows.map((r) => r.key)).not.toContain("window re-optimization");
  expect(rows).toHaveLength(1);
});

test("the note says WHAT WAS HELD — which is what makes 'your move' readable", () => {
  expect(LOCAL_NOTE).toContain("everything else held");
});

test("the founder's nudge reads as $0, not as an absence", () => {
  // $0.00 is the ANSWER here, and the row is drawn to say so. A suppressed row
  // would leave a planner unable to tell "this costs nothing" from "we didn't
  // price it".
  const rows = attributionRows(local({ cost_delta_abs: 0.0, move_delta_abs: 0.0 }));
  expect(rows).toHaveLength(1);
  expect(signedMoney(rows[0].value)).toBe("$0");
});

test("a local price with no move part draws nothing rather than a bare label", () => {
  expect(attributionRows(local({ move_delta_abs: null }))).toBeNull();
});

test("the SPLIT reading is untouched — 4B.5's card still works", () => {
  // A negative control in the other direction: the amendment must not have been
  // implemented by deleting the split. A payload from the re-solve path still
  // draws two rows.
  const rows = attributionRows({
    attribution: "split", cost_delta_abs: -11975.83,
    reopt_delta_abs: -11600.0, move_delta_abs: -375.83,
  });
  expect(rows.map((r) => r.key)).toEqual(["window re-optimization", "your move"]);
});

test("an unknown attribution is unsplit, never guessed", () => {
  expect(attributionRows({ attribution: "something-new", move_delta_abs: 5 }))
    .toBeNull();
  expect(UNSPLIT_NOTE).toBe("includes window re-optimization");
});

// ---------------------------------------------------------------------------
// CLAUSE (3) — the opportunity is its own thing
// ---------------------------------------------------------------------------

const withOpportunity = (over = {}) => local({
  opportunity: {
    found: true, delta_abs: -239824.8, moved_op_count: 226,
    affected_orders: [{ work_order: "ORD-000070", tardiness_delta: -88340.0 }],
    sentence: "the search found a schedule $239,824.80 cheaper for this window",
    ...over,
  },
});

test("an opportunity renders as its OWN block with its OWN delta", () => {
  const o = opportunityBlock(withOpportunity());
  expect(o.delta_abs).toBe(-239824.8);
  expect(o.movedOps).toBe(226);
  expect(o.affected).toHaveLength(1);
});

test("the opportunity's money is NOT the move's money", () => {
  // The single most important property on this card. The founder's incident was
  // a fragment of an opportunity worn as a price. They are different numbers
  // from different questions and nothing may add them.
  const r = withOpportunity();
  const rows = attributionRows(r);
  const o = opportunityBlock(r);
  expect(rows[0].value).toBe(0.0);
  expect(o.delta_abs).not.toBe(rows[0].value);
  // and the move's own affected list is untouched by the search's
  expect(r.affected_orders || []).toHaveLength(0);
});

test("no opportunity means no block — a card never grows an empty heading", () => {
  expect(opportunityBlock(local())).toBeNull();
  expect(opportunityBlock(local({ opportunity: {} }))).toBeNull();
  expect(opportunityBlock(local({ opportunity: { found: false, delta_abs: 12 } })))
    .toBeNull();
  expect(opportunityBlock(null)).toBeNull();
});

test("a search that found nothing CHEAPER is not an opportunity", () => {
  // A baseline DEARER than the incumbent says something about the search, not
  // about the plan, and offering it would be offering a downgrade.
  expect(opportunityBlock(local({
    opportunity: { found: false, delta_abs: 400.0,
                   sentence: "the search found nothing cheaper" },
  }))).toBeNull();
});
