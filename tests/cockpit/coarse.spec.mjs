// THE COARSE ZONE's DENSITY BAND — screenshot coverage (Session 4B.6a CU4).
//
// 4B.6 shipped the band (src/cockpit/src/coarse.js) with NO browser coverage:
// the committed rolling fixture predated the 2026-07-26 determinism fixes and
// could not be regenerated, so there was no document carrying a coarse zone to
// render. CU4 regenerated it under authorization; this is the coverage it
// unblocked.
//
// Three states, and the clause each one guards:
//   * POPULATED   — a real coarse zone renders as a GRID OF LOAD CELLS and
//                   NEVER as a bar (clause 6: bars mean placement).
//   * EMPTY       — a coarse zone that ran over an empty tray renders its
//                   header and no rows: it claims nothing rather than hiding.
//   * BINDING     — a hot cell's TOOLTIP states its own arithmetic (load
//                   against derated capacity) and carries the 4B.6a CU2(b)
//                   caveat that the arithmetic ran over a PARTIAL POPULATION.
//
// Runs on BOTH data-themes, like every other rendering spec.
import { test, expect } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const SHOTS = resolve(dirname(fileURLToPath(import.meta.url)), "shots");
mkdirSync(SHOTS, { recursive: true });
const theme = () => test.info().project.metadata?.theme || "light";
const shot = (page, name) => page.screenshot({ path: resolve(SHOTS, `${name}__${theme()}.png`) });

const ROLLING = "sched-rolling-fixture";      // plant's own declared derate 0.85
const EMPTY = "sched-rolling-empty";          // empty tray -> empty band
const HOT = "sched-rolling-coarse-hot";       // tight declared derate -> hot cells

async function boot(page, schedule) {
  await page.request.post("/__test__/reset").catch(() => {});
  await page.goto(`/?schedule=${schedule}&theme=${theme()}`);
  await page.waitForFunction(() => window.__cockpit && window.__cockpit.ready === true, { timeout: 20000 });
  expect(await page.evaluate(() => window.__cockpit.error || null), "booted clean").toBeNull();
}

const probe = (page) => page.evaluate(() =>
  (window.__cockpit.coarseBand && window.__cockpit.coarseBand.probe()) || null);

// Session 4B.28 Item 2(a): the coarse dock now ships COLLAPSED by default
// (screen room — a stranger does not need a density grid in their first ten
// seconds). Its CONTENT is unchanged and its BADGE states the binding count
// while collapsed, so these specs expand it and then assert exactly what they
// always asserted. A spec that quietly stopped opening the dock would be
// testing the collapse, not the band.
const expand = (page) => page.evaluate(() => {
  const d = window.__cockpit.docks && window.__cockpit.docks.coarse;
  if (d && !d.isOpen()) d.set(true);
});

// --- POPULATED -----------------------------------------------------------
test("the density band renders LOAD cells, and never a bar", async ({ page }) => {
  await boot(page, ROLLING);
  await expand(page);
  const band = page.locator("#coarse-band");
  await expect(band, "the band is mounted").toBeVisible();
  const p = await probe(page);
  expect(p, "the band exposes its probe").not.toBeNull();
  expect(p.buckets, "bucket columns").toBeGreaterThan(0);
  expect(p.resources, "resource rows").toBeGreaterThan(0);
  expect(p.cells, "one cell per resource x bucket").toBe(p.buckets * p.resources);
  // CLAUSE (6): bars mean placement. The band must never emit one.
  expect(p.bars, "the band emitted a bar element").toBe(0);
  // it says what it is, and it never says "scheduled".
  await expect(band.locator(".cb-title")).toContainText("load, not placement");
  expect((await band.innerText()).toLowerCase()).not.toContain("scheduled");
  await shot(page, "cb1_band_populated");
});

test("the band states the derate AND its provenance", async ({ page }) => {
  await boot(page, ROLLING);
  await expand(page);
  const p = await probe(page);
  // CLAUSE (3): a defaulted derate can never read as the plant's own choice.
  expect(["declared", "defaulted"]).toContain(p.derateProvenance);
  const note = await page.locator("#coarse-band .cb-note").innerText();
  if (p.derateProvenance === "declared") {
    expect(note).toContain("declared");
  } else {
    // 4B.6a CU2(d): the ABSENCE is loud, not merely stated.
    expect(note.toLowerCase()).toMatch(/no capacity margin declared|a default, not declared/);
  }
});

// --- EMPTY ---------------------------------------------------------------
test("a coarse zone over an empty tray renders an EMPTY band, not a hidden one",
  async ({ page }) => {
    await boot(page, EMPTY);
    await expand(page);
    const band = page.locator("#coarse-band");
    await expect(band, "the band is still mounted when there is no load").toBeVisible();
    const p = await probe(page);
    expect(p.resources, "no resource rows: nothing beyond the horizon").toBe(0);
    expect(p.cells, "no cells").toBe(0);
    expect(p.bars).toBe(0);
    await expect(band.locator(".cb-title")).toContainText("load, not placement");
    await shot(page, "cb2_band_empty");
  });

// --- BINDING -------------------------------------------------------------
test("a binding cell's tooltip states its own arithmetic and its caveat",
  async ({ page }) => {
    await boot(page, HOT);
    await expand(page);
    const p = await probe(page);
    expect(p.hot, "at least one machine-week is at capacity").toBeGreaterThan(0);
    // the arithmetic, never just the colour
    const hot = page.locator("#coarse-band .cb-cell.cb-hot").first();
    const title = await hot.getAttribute("title");
    expect(title, "load against capacity, in minutes").toMatch(/\d+ min of work against \d+ min of capacity \(\d+%\)/);
    expect(title, "an estimate over whole weeks, never a placement").toContain("not a placement");
    expect(title).not.toContain("scheduled");
    // 4B.6a CU2(b): a cell reading 60% over a PARTIAL POPULATION is not 60%.
    expect(p.unmodelableCount, "this fixture excludes ops, which is the point")
      .toBeGreaterThan(0);
    expect(title, "the tooltip carries the uncounted-population caveat")
      .toContain("not in this figure");
    expect(p.cellsWithUncountedNote, "EVERY cell carries it, not just the footer")
      .toBe(p.cells);
    // and the footer says it too, in words
    await expect(page.locator("#coarse-band .cb-foot"))
      .toContainText("every load here is understated");
    await hot.hover();
    await shot(page, "cb3_band_binding_cell");
  });

test("a band with nothing excluded invents no caveat", async ({ page }) => {
  await boot(page, ROLLING);
  await expand(page);
  const p = await probe(page);
  // The real board's plant excludes nothing at demo density; the caveat must
  // appear only when there is something to caveat (both directions, CU2).
  if (p.unmodelableCount === 0) {
    expect(p.cellsWithUncountedNote).toBe(0);
    await expect(page.locator("#coarse-band .cb-foot")).toHaveCount(0);
    const title = await page.locator("#coarse-band .cb-cell").first().getAttribute("title");
    expect(title).not.toContain("not in this figure");
  } else {
    expect(p.cellsWithUncountedNote).toBe(p.cells);
  }
});
