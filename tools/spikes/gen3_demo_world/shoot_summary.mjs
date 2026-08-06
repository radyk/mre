// Session W2.3 -- screenshot the summary screen of a LIVE board, both themes.
//
// NOT the fixture harness. `tests/cockpit/summary.spec.mjs` drives a scripted
// document through the hermetic fixture server, which is right for asserting
// the four progress states but proves nothing about what a planner sees on a
// real 386-bar board served by the real API. This drives the DEV cockpit
// (localhost:5175) against a REGISTERED schedule id, so what it captures is the
// product.
//
//   node tools/spikes/gen3_demo_world/shoot_summary.mjs rolling-xxxx-xxx
//
// It also prints the figures it found in the DOM, because a screenshot is
// evidence a human has to read and a printed assertion is evidence a session
// can quote.
import { chromium } from "../../../tests/cockpit/node_modules/playwright/index.mjs";
import { mkdirSync } from "node:fs";

const SCHEDULE = process.argv[2];
const BASE = process.env.COCKPIT_BASE || "http://localhost:5175";
const OUT = "_w23_scratch/shots";

if (!SCHEDULE) {
  console.error("usage: node shoot_summary.mjs <schedule_id>");
  process.exit(2);
}
mkdirSync(OUT, { recursive: true });

const text = async (page, sel) => {
  const n = await page.locator(sel).count();
  return n ? (await page.locator(sel).first().innerText()).replace(/\s+/g, " ").trim() : null;
};

const browser = await chromium.launch();
let bad = 0;

for (const theme of ["light", "dark"]) {
  const page = await browser.newPage({
    viewport: { width: 1540, height: 900 }, deviceScaleFactor: 2,
  });
  await page.goto(`${BASE}/?theme=${theme}&schedule=${SCHEDULE}`,
                  { waitUntil: "networkidle" });
  await page.waitForSelector("#summary-open", { timeout: 60_000 });
  await page.click("#summary-open");
  await page.waitForSelector("#summary-screen", { timeout: 30_000 });
  await page.waitForTimeout(600);           // let the curve settle before the shot

  const state = await page.locator("#sm-progress").getAttribute("data-state");
  const priced = await page.locator("#sm-priced").count();
  const zone = await text(page, "#sm-trail-zone");

  console.log(`\n[${theme}]  progress state = ${state}   priced block = ${priced}`);
  console.log(`  total        : ${await text(page, "#sm-total")}`);
  console.log(`  headline     : ${await text(page, "#sm-progress-story")}`);
  for (const row of await page.locator("#sm-priced .sm-priced-row").all()) {
    console.log(`  priced row   : ${(await row.innerText()).replace(/\s+/g, " ").trim()}`);
  }
  console.log(`  window key   : ${await text(page, "#sm-window-key")}`);
  console.log(`  proof floor  : ${await text(page, "#sm-proof-floor")}`);

  // R-SP1 clause (3) live: the zone is the scaled objective's, in both regimes.
  if (zone && zone.includes("$")) {
    console.log("  ** FAIL: a dollar sign entered the solver-units zone");
    bad += 1;
  } else {
    console.log("  zone         : money-free (R-DP12 / R-SP1 clause 3) OK");
  }
  if (state !== "present" || priced !== 1) {
    console.log(`  ** FAIL: expected a PRICED, PRESENT trail on this board`);
    bad += 1;
  }

  // THE STATISTICS ROW (contract 1.17). W2.1's rule was that a statistic we
  // cannot source is a NAMED GAP, not a number; W2.2 landed three rollups and
  // left the gap machinery in place with an empty list. So both halves are
  // read here: every tile that rendered, and whether anything is still named
  // as missing.
  // Every tile carries `data-source` — the document path it was read from. That
  // is the screen's own provenance rule made checkable, so it is read here
  // rather than the number alone: a figure with no source is the defect.
  const tiles = await page.locator("#sm-tiles .sm-tile").all();
  console.log(`  stats tiles  : ${tiles.length}`);
  for (const t of tiles) {
    const src = await t.getAttribute("data-source");
    const body = (await t.innerText()).replace(/\s+/g, " ").trim();
    console.log(`     ${body.padEnd(40)} <- ${src || "** NO SOURCE **"}`);
    if (!src) bad += 1;
  }
  console.log(`  named gaps   : ${await page.locator("#sm-gaps").count()
                                  ? await text(page, "#sm-gaps") : "none (empty list)"}`);
  const utilRows = await page.locator("#sm-util-table tbody tr").count();
  console.log(`  util rows    : ${utilRows}`);
  console.log(`  util defn    : ${(await text(page, "#sm-util-definition") || "").slice(0, 90)}...`);
  if (!tiles.length || !utilRows) {
    console.log("  ** FAIL: the 1.17 rollups did not render");
    bad += 1;
  }

  // Two shots: the money+search story, and the statistics below it. An element
  // screenshot of the whole screen runs past the rendered region (the screen
  // scrolls internally), which is why this is two captures and not one.
  await page.locator("#summary-screen").screenshot({
    path: `${OUT}/summary_${theme}.png`,
  });
  await page.locator("#sm-stats").scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${OUT}/summary_stats_${theme}.png` });
  console.log(`  shots        : ${OUT}/summary_${theme}.png + summary_stats_${theme}.png`);
  await page.close();
}

await browser.close();
console.log(bad ? `\n${bad} check(s) FAILED` : "\nall checks OK, both themes");
process.exit(bad ? 1 : 0);
