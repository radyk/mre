// Row-intelligence JS port tests (Session 4.2 CU4). Pure-JS (the "logic"
// project — no browser, theme-free): import the framework-free module and
// assert it produces the SAME numbers as the Python canonical definition
// (src/mre/modules/row_intelligence.py) on the SHARED fixtures. If the two ever
// drift, the planner's visible-window utilization / booked-through / next-gap
// stops being the solver's window arithmetic — so this file and
// tests/test_row_intelligence.py both read rowstats_cases.json.
import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import {
  rowUtilization, bookedThrough, nextAvailableGap, openCapacity,
} from "../../src/cockpit/legality/rowstats.js";

const FIX = resolve(dirname(fileURLToPath(import.meta.url)), "fixtures");
const CASES = JSON.parse(readFileSync(resolve(FIX, "rowstats_cases.json"), "utf-8")).cases;

for (const c of CASES) {
  test(`rowstats parity — ${c.name}`, () => {
    const [lo, hi] = c.util_window;
    const util = rowUtilization(c.windows, c.occupancy, lo, hi);
    if (c.util === null) {
      expect(util).toBeNull();
    } else {
      expect(util).not.toBeNull();
      expect(Math.round(util * 1e4) / 1e4).toBeCloseTo(c.util, 4);
    }
    expect(bookedThrough(c.occupancy)).toBe(c.booked_through);
    expect(nextAvailableGap(c.windows, c.occupancy, c.gap_from)).toBe(c.next_gap);
  });
}

test("openCapacity clips to the window", () => {
  expect(openCapacity([[0, 100], [200, 300]], 50, 250)).toBe(100);
});

test("utilization never exceeds 1 when occupancy overflows the open window", () => {
  expect(rowUtilization([[0, 100]], [[0, 500]], 0, 100)).toBe(1);
});
