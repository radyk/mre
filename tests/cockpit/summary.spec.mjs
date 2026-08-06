// THE SUMMARY SCREEN, RENDERED (Session W2.1, R-SP1).
//
// Driven THROUGH THE USER'S DOOR — a real click on the strip's `summary`
// button, never a direct call into the module (4B.28 §5a.123: a control driven
// past its own entry point stays green against the defect it was written for).
//
// The three trail states are produced by rewriting the document the API serves,
// because the committed fixtures were captured before the trail existed — which
// is itself the ABSENT state, and is asserted unrewritten.
import { test, expect } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const SHOTS = resolve(dirname(fileURLToPath(import.meta.url)), "shots");
mkdirSync(SHOTS, { recursive: true });
const theme = () => test.info().project.metadata?.theme || "light";
const shot = (page, name) =>
  page.screenshot({ path: resolve(SHOTS, `${name}__${theme()}.png`), fullPage: true });

const ROLLING = "sched-rolling-fixture";

// R-SP1 clause (2)/(3), as the server composes them. The spec asserts these
// appear VERBATIM in the render — the cockpit must not paraphrase the
// disclosure that keeps the improvement figure honest.
const CLAUSE_2 =
  "This compares the solver's own first workable plan with the plan it "
  + "finished on. It is not a comparison with your current schedule, your "
  + "planners, or any other baseline — the solver's first plan is not what a "
  + "planner would have made.";
const CLAUSE_3 =
  "The figures in this trail are the solver's own internal cost measure, not "
  + "dollars. The dollar figure for this plan is the ledger above; it belongs "
  + "to the finished plan and is not differenced against an earlier one.";

const TRAIL_PRESENT = {
  stage: "cost", window_key: "2026-01-12T00:00:00+00:00",
  count: 4, first: 1_240_000, final: 980_000,
  improvement_abs: 260_000, improvement_pct: 20.967741935,
  flat: false, best_bound: 910_000, gap: 0.0714,
  objective_unit: "objective_units",
  headline: "The solver's first workable plan scored 1,240,000; it finished on "
          + "a plan scoring 980,000 — 21.0% better by its own cost measure.",
  clause_2_label: CLAUSE_2, clause_3_label: CLAUSE_3,
  incumbents: [
    { index: 1, objective: 1_240_000, elapsed_s: 0.42 },
    { index: 2, objective: 1_090_000, elapsed_s: 1.31 },
    { index: 3, objective: 1_010_000, elapsed_s: 2.87 },
    { index: 4, objective: 980_000, elapsed_s: 4.05 },
  ],
};

const TRAIL_FLAT = {
  ...TRAIL_PRESENT, count: 1, flat: true, final: 1_240_000,
  improvement_abs: 0, improvement_pct: 0,
  headline: "The solver found one workable plan, scoring 1,240,000 on its own "
          + "cost measure, and did not improve on it within its budget.",
  incumbents: [{ index: 1, objective: 1_240_000, elapsed_s: 0.42 }],
};

/** Serve the fixture document with `solver.progress` set (or left absent). */
async function boot(page, { progress = null, schedule = ROLLING } = {}) {
  if (progress) {
    await page.route(`**/schedules/${schedule}`, async (route) => {
      const res = await route.fetch();
      const body = await res.json();
      body.data.solver.progress = progress;
      await route.fulfill({ response: res, body: JSON.stringify(body) });
    });
  }
  await page.goto(`/?schedule=${schedule}&theme=${theme()}`);
  await page.waitForFunction(() => window.__cockpit && window.__cockpit.ready === true,
                             { timeout: 20000 });
}

/** The user's door: click the strip button and wait for the screen. */
async function openSummary(page) {
  await page.click("#summary-open");
  await page.waitForSelector("#summary-screen", { timeout: 5000 });
}

// ======================================================================
// STATE 1 — PRESENT
// ======================================================================

test("trail PRESENT — the story, the trail, the curve and the proof floor", async ({ page }) => {
  await boot(page, { progress: TRAIL_PRESENT });
  await openSummary(page);

  await expect(page.locator("#sm-progress")).toHaveAttribute("data-state", "present");
  await expect(page.locator("#sm-progress-story"))
    .toHaveText(TRAIL_PRESENT.headline);

  // one row per incumbent, first and last named rather than numbered
  const rows = page.locator("#sm-trail tbody tr");
  await expect(rows).toHaveCount(4);
  await expect(rows.nth(0).locator(".sm-k")).toHaveText("first workable");
  await expect(rows.nth(3).locator(".sm-k")).toHaveText("final");
  await expect(page.locator("#sm-curve svg")).toBeVisible();

  // clause (4): the proof floor and gap ride WITH the story, in the gap rider's
  // own vocabulary.
  const proof = await page.locator("#sm-proof-floor").innerText();
  expect(proof).toContain("not proven");
  expect(proof).toContain("a cheaper plan may exist and could be up to");
  await shot(page, "summary_trail_present");
});

test("a long trail is capped in the table and SAYS SO — no silent truncation", async ({ page }) => {
  // A real board's search produces dozens of incumbents (46 on an eight-job
  // specimen). A table showing twelve of them without saying so would read as
  // the whole search, which is the silent-cap failure this repo keeps naming.
  const many = Array.from({ length: 46 }, (_, i) => ({
    index: i + 1, objective: 6515 - i * 130, elapsed_s: 0.05 * (i + 1),
  }));
  await boot(page, { progress: {
    ...TRAIL_PRESENT, count: 46, first: 6515, final: many[45].objective,
    incumbents: many } });
  await openSummary(page);
  const rows = await page.locator("#sm-trail tbody tr").count();
  expect(rows).toBeLessThan(46);
  const cap = await page.locator("#sm-trail-cap").innerText();
  expect(cap).toContain(`${rows} of 46`);
  expect(cap).toContain("plots all 46");
  // the two that matter are never the ones dropped
  await expect(page.locator("#sm-trail tbody tr").first().locator(".sm-v").first())
    .toHaveText("6,515");
  // and the curve draws every point
  const dots = await page.locator("#sm-curve circle").count();
  expect(dots).toBe(46);
});

test("clause (2) and clause (3) render VERBATIM", async ({ page }) => {
  // The labels are the whole reason the improvement figure is publishable. A
  // paraphrase is a different claim, so the assertion is exact-match.
  await boot(page, { progress: TRAIL_PRESENT });
  await openSummary(page);
  await expect(page.locator("#sm-clause-2")).toHaveText(CLAUSE_2);
  await expect(page.locator("#sm-clause-3")).toHaveText(CLAUSE_3);
});

test("no dollar sign touches the trail (R-DP12 / R-SP1 clause 3)", async ({ page }) => {
  await boot(page, { progress: TRAIL_PRESENT });
  await openSummary(page);
  for (const sel of ["#sm-trail", "#sm-progress-story", "#sm-proof-floor"]) {
    const text = await page.locator(sel).innerText();
    expect(text, `${sel} rendered the scaled objective as money`).not.toContain("$");
  }
  // …while the ledger, which IS money, keeps its dollar sign.
  await expect(page.locator("#sm-total")).toContainText("$");
});

test("clause (1) — the trail names the one window it belongs to", async ({ page }) => {
  await boot(page, { progress: TRAIL_PRESENT });
  await openSummary(page);
  const t = await page.locator("#sm-window-key").innerText();
  expect(t).toContain("never added together");
  // R-TZ1: one declared clock, and the screen says which.
  const strip = await page.locator(".clock-label").innerText();
  expect(t).toContain(strip);
});

// ======================================================================
// STATE 2 — FLAT
// ======================================================================

test("trail FLAT — one incumbent is told, not hidden, and no curve is drawn", async ({ page }) => {
  await boot(page, { progress: TRAIL_FLAT });
  await openSummary(page);
  await expect(page.locator("#sm-progress")).toHaveAttribute("data-state", "flat");
  await expect(page.locator("#sm-progress-story")).toContainText("did not improve");
  // a one-point trail has no table and no curve — there is no shape to draw
  await expect(page.locator("#sm-trail")).toHaveCount(0);
  await expect(page.locator("#sm-curve svg")).toHaveCount(0);
  // but the proof floor still renders (clause 4)
  await expect(page.locator("#sm-proof-floor")).toBeVisible();
  await shot(page, "summary_trail_flat");
});

// ======================================================================
// STATE 3 — ABSENT (the committed fixture, unrewritten)
// ======================================================================

test("trail ABSENT — a pre-change board says so and reconstructs nothing", async ({ page }) => {
  await boot(page);                    // no rewrite: the fixture has no trail
  await openSummary(page);
  await expect(page.locator("#sm-progress")).toHaveAttribute("data-state", "absent");
  const t = await page.locator("#sm-progress .sm-absent").innerText();
  expect(t).toContain("before the solver kept a record of its own search");
  expect(t).toContain("Nothing was reconstructed");
  // no trail furniture at all — an absent state must not render an empty one
  await expect(page.locator("#sm-trail")).toHaveCount(0);
  await expect(page.locator("#sm-curve svg")).toHaveCount(0);
  await expect(page.locator("#sm-clause-2")).toHaveCount(0);
  await shot(page, "summary_trail_absent");
});

// ======================================================================
// DOLLARS FIRST, AND THE HONEST GAP
// ======================================================================

test("dollars first — the ledger total precedes the search story on the page", async ({ page }) => {
  await boot(page, { progress: TRAIL_PRESENT });
  await openSummary(page);
  const money = await page.locator("#sm-money").boundingBox();
  const progress = await page.locator("#sm-progress").boundingBox();
  const stats = await page.locator("#sm-stats").boundingBox();
  expect(money.y).toBeLessThan(progress.y);
  expect(progress.y).toBeLessThan(stats.y);
  await expect(page.locator("#sm-total .sm-total-lbl")).toHaveText("total ledger cost");
});

test("the three unsourceable statistics are named on the screen", async ({ page }) => {
  await boot(page, { progress: TRAIL_PRESENT });
  await openSummary(page);
  const gaps = page.locator("#sm-gaps .sm-gaplist li");
  await expect(gaps).toHaveCount(3);
  const text = await page.locator("#sm-gaps").innerText();
  for (const label of ["late / on-time orders", "utilization by machine",
                       "total changeover minutes"]) {
    expect(text).toContain(label);
  }
  // each names where it SHOULD come from — a gap with no address is a shrug
  expect(text).toContain("Should come from");
});

test("every rendered cost row names the document field it came from", async ({ page }) => {
  // The provenance rule, asserted on the DOM: a figure with no `data-source` is
  // a figure the frontend computed.
  await boot(page, { progress: TRAIL_PRESENT });
  await openSummary(page);
  const missing = await page.evaluate(() =>
    [...document.querySelectorAll("#sm-cost-table tbody tr, #sm-tiles .sm-tile")]
      .filter((n) => !n.dataset.source).length);
  expect(missing).toBe(0);
});

// ======================================================================
// THE PRE/POST WALL
// ======================================================================

test("the screen carries no solve control, no parameter and no Gatehouse element",
  async ({ page }) => {
    await boot(page, { progress: TRAIL_PRESENT });
    await openSummary(page);
    const root = page.locator("#summary-screen");
    // the ONLY interactive element is the close button
    const controls = await root.locator("button, input, select, textarea").count();
    expect(controls).toBe(1);
    await expect(root.locator("#sm-close")).toBeVisible();
    await expect(root).toContainText("read-only · post-solve");
  });

test("close returns the planner to the board with nothing changed", async ({ page }) => {
  await boot(page, { progress: TRAIL_PRESENT });
  await openSummary(page);
  await page.click("#sm-close");
  await expect(page.locator("#summary-screen")).toHaveCount(0);
  await expect(page.locator("#tl")).toBeVisible();
});
