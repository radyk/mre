// CU1 (Session 4B.5) — the delta card's ATTRIBUTION, as pure reads.
//
// No rendering: runs once, theme-free, in the `logic` project (like legality /
// rowstats / freshness / schedulepicker). What is pinned here is the reading
// rule, not the arithmetic — the split itself is computed and proven server-side
// (tests/test_delta_attribution.py). The card's job is to draw the split when
// there is one, say so plainly when there is not, and never invent a partial.
import { test, expect } from "@playwright/test";
import {
  UNSPLIT_NOTE, attributionRows, signedMoney,
} from "../../src/cockpit/src/drag/sandboxui.js";

const split = (over = {}) => ({
  outcome: "verdict", feasible: true, cost_delta_abs: -11975.83,
  attribution: "split", reopt_delta_abs: -11600.0, move_delta_abs: -375.83,
  baseline_total_cost: 88775.83, attribution_note: "", ...over,
});

test("a proven baseline draws two rows, re-optimization first, your move last", () => {
  const rows = attributionRows(split());
  expect(rows.map((r) => r.key)).toEqual(["window re-optimization", "your move"]);
  expect(rows.map((r) => r.value)).toEqual([-11600.0, -375.83]);
  // exactly one row is the planner's own — it is what the card emphasizes
  expect(rows.filter((r) => r.own).map((r) => r.key)).toEqual(["your move"]);
});

test("the drawn rows sum to the headline the card is already showing", () => {
  const r = split();
  const rows = attributionRows(r);
  const sum = Number((rows[0].value + rows[1].value).toFixed(2));
  expect(sum).toBe(r.cost_delta_abs);
});

test("an unavailable attribution draws NO rows (the note is the caller's job)", () => {
  expect(attributionRows(split({
    attribution: "unavailable", reopt_delta_abs: null, move_delta_abs: null,
    attribution_note: "the window could not be re-solved without your move "
                      + "inside the budget",
  }))).toBeNull();
});

test("a HALF-attribution is not an attribution — one missing part draws nothing", () => {
  // the failure this guards: a card that shows "your move −$375.83" with no
  // reference to measure it against reads as more certain than the unsplit total.
  expect(attributionRows(split({ reopt_delta_abs: null }))).toBeNull();
  expect(attributionRows(split({ move_delta_abs: null }))).toBeNull();
});

test("a card with no attribution field at all is unsplit, never assumed", () => {
  // every pre-CU1 canned payload, and any future degrade: absence is unsplit.
  expect(attributionRows({ outcome: "verdict", feasible: true,
                           cost_delta_abs: -100 })).toBeNull();
  expect(attributionRows(null)).toBeNull();
  expect(attributionRows({})).toBeNull();
});

test("a zero move part is DRAWN, not suppressed — it is the answer, not an absence", () => {
  // the founder's specimen resolves to exactly this: the whole delta was
  // re-optimization and the gesture bought nothing. Hiding the row would put the
  // card back where it started.
  const rows = attributionRows(split({ reopt_delta_abs: -11975.83,
                                       move_delta_abs: 0.0 }));
  expect(rows).not.toBeNull();
  expect(rows[1].value).toBe(0.0);
  expect(signedMoney(rows[1].value)).toBe("$0");
});

test("signed money reads the same everywhere the card shows a dollar figure", () => {
  expect(signedMoney(-11600)).toBe("−$11,600");
  expect(signedMoney(375.83)).toBe("+$375.83");
  expect(signedMoney(0)).toBe("$0");
  expect(signedMoney(0.004)).toBe("$0");      // a rounding residue is not a sign
  expect(signedMoney(-0.004)).toBe("$0");
  expect(signedMoney(null)).toBe("");
});

test("the unsplit note is one wording, shared with the server", () => {
  // mre.modules.sandbox.UNSPLIT_NOTE — the same sentence in two languages.
  expect(UNSPLIT_NOTE).toBe("includes window re-optimization");
});

// --- Session 4B.6a CU4(4): THE SPLIT, ASSERTED ON REAL SOLVER FIGURES -----
//
// Every assertion above runs against a hand-written object. The COMMITTED
// rolling fixture's split was hand-written too: 4B.5 could not regenerate the
// fixture (it predated the 2026-07-26 determinism fixes), so its
// `reopt_delta_abs: -9500.0 / move_delta_abs: -294.53` were SYNTHESIZED to the
// shape and the decomposition-sums invariant had never once been checked
// against numbers a solver actually produced.
//
// CU4 regenerated the fixture under authorization. These figures come from a
// real `sandbox_pin_resolve(baseline=True)` — two solves of the same window,
// one with the pin and one without — and the sum is now asserted on them.
import { readFileSync } from "node:fs";
import { resolve as _resolve, dirname as _dirname } from "node:path";
import { fileURLToPath as _fileURLToPath } from "node:url";

const _FIX = _resolve(_dirname(_fileURLToPath(import.meta.url)), "fixtures", "rolling");
const REAL = JSON.parse(readFileSync(_resolve(_FIX, "sandbox.json"), "utf8"));

test("the committed fixture's split sums exactly, on REAL solver figures", () => {
  const cards = [REAL.default, ...Object.values(REAL.by_op)]
    .filter((c) => c && c.attribution === "split");
  expect(cards.length, "the fixture carries at least one split card").toBeGreaterThan(0);
  for (const c of cards) {
    // not the synthesized pair this replaced — a guard against a future
    // hand-edit quietly restoring them.
    expect(c.reopt_delta_abs, "the synthesized -9500.0 is gone").not.toBe(-9500.0);
    expect(c.move_delta_abs, "the synthesized -294.53 is gone").not.toBe(-294.53);
    // a real baseline solve happened, and the card says what it cost
    expect(c.baseline_total_cost).not.toBeNull();
    expect(c.baseline_wall_time_s).toBeGreaterThan(0);
    // DECOMPOSITION-SUMS, on numbers a solver produced
    expect(Number((c.reopt_delta_abs + c.move_delta_abs).toFixed(2)))
      .toBe(Number(c.cost_delta_abs.toFixed(2)));
    // and the rows the card draws are those same two numbers
    const rows = attributionRows(c);
    expect(rows.map((r) => r.value)).toEqual([c.reopt_delta_abs, c.move_delta_abs]);
  }
});

test("an unprovable baseline in the real fixture stays UNSPLIT, never half-split", () => {
  const unavailable = Object.values(REAL.by_op)
    .filter((c) => c && c.attribution === "unavailable");
  for (const c of unavailable) {
    expect(c.reopt_delta_abs).toBeNull();
    expect(c.move_delta_abs).toBeNull();
    expect(attributionRows(c)).toBeNull();
  }
});
