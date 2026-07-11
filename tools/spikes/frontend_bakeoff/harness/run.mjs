// Candidate-agnostic Playwright screenshot harness for the Phase-3 drag cockpit.
// SURVIVES the spike (interim-A infrastructure). It drives a scripted
// grab / drag / drop through a small, stable page contract and captures each
// state; it also performs a REAL pointer drag to prove the candidate is
// driveable headlessly (spike criterion 5 — a candidate that can't be driven
// this way is a HARD FAIL).
//
// Page contract (both candidates expose it):
//   window.__spike.ready      -> true once the fixture is loaded
//   window.__spike.candidate  -> "A" | "B"
//   window.__spike.grab()             -> begin the interaction (shading+ghosts)
//   window.__spike.moveToGhost(i)     -> snap the tentative onto ghost i
//   window.__spike.moveToTime(iso,{alt,row}) -> snap to a time (alt disables snap)
//   window.__spike.setAlt(bool)
//   window.__spike.drop()             -> finalize a tentative bar
//   window.__spike.reset()
//   window.__spike.getState()         -> { phase, tentative, latency }
//
// Usage:  node harness/run.mjs [baseURL]
// Env:    SHOTS_DIR (default ./shots)

import { chromium } from "playwright";
import { mkdirSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, resolve } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const BASE = process.argv[2] || "http://localhost:5173";
const SHOTS = process.env.SHOTS_DIR || resolve(__dirname, "..", "shots");
mkdirSync(SHOTS, { recursive: true });

const ONLY = process.env.ONLY; // "a" | "b" to run one candidate
const CANDIDATES = [
  { id: "a", url: `${BASE}/candidate_a.html` },
  { id: "b", url: `${BASE}/candidate_b.html` },
].filter((c) => !ONLY || c.id === ONLY);

async function waitReady(page) {
  await page.waitForFunction(() => window.__spike && window.__spike.ready === true, { timeout: 15000 });
}

async function shot(page, name) {
  const path = resolve(SHOTS, `${name}.png`);
  await page.screenshot({ path });
  return path;
}

async function driveScripted(page, id, report) {
  // idle
  await shot(page, `${id}_1_idle`);
  // grab -> Tier-0 shading + ghosts; measure latency
  await page.evaluate(() => window.__spike.grab());
  await page.waitForTimeout(120);
  const st = await page.evaluate(() => window.__spike.getState());
  report.latencyMs = st.latency;
  await shot(page, `${id}_2_grab_shaded`);
  // drag onto a priced ghost (dynamic semantic snap target)
  await page.evaluate(() => window.__spike.moveToGhost(2));
  await page.waitForTimeout(80);
  const st2 = await page.evaluate(() => window.__spike.getState());
  report.snapOnGhost = st2.tentative?.snappedTo;
  report.ghostDeltaShown = st2.tentative?.deltaCost;
  await shot(page, `${id}_3_snap_ghost`);
  // snap to predecessor-finish (magnet), then Alt-free to show snap disabled
  await page.evaluate(() => {
    const t = window.__SPIKE_PREDFINISH; window.__spike.moveToTime(t, { alt: false });
  });
  await page.waitForTimeout(60);
  await shot(page, `${id}_4_snap_predfinish`);
  // drop -> tentative hatched bar
  await page.evaluate(() => window.__spike.drop());
  await page.waitForTimeout(80);
  const st3 = await page.evaluate(() => window.__spike.getState());
  report.droppedPhase = st3.phase;
  await shot(page, `${id}_5_tentative_drop`);
  await page.evaluate(() => window.__spike.reset());
}

// Real pointer drag over the actual grab element — the honest drivability test.
async function driveRealPointer(page, id, report) {
  try {
    const box = await page.evaluate(() => {
      const el = document.querySelector("[data-grab]") || document.querySelector(".grabitem");
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
    });
    if (!box) { report.realPointer = "no grab element found"; return; }
    await page.mouse.move(box.x, box.y);
    await page.mouse.down();
    await page.mouse.move(box.x + 40, box.y + 60, { steps: 6 });
    await page.mouse.move(box.x + 120, box.y + 120, { steps: 8 });
    await page.waitForTimeout(60);
    await shot(page, `${id}_6_realdrag_mid`);
    const mid = await page.evaluate(() => window.__spike.getState());
    await page.mouse.up();
    await page.waitForTimeout(60);
    await shot(page, `${id}_7_realdrag_drop`);
    report.realPointer = mid.phase === "grabbing" ? "OK (grab engaged via real pointer)" : `phase=${mid.phase}`;
    await page.evaluate(() => window.__spike.reset());
  } catch (e) {
    report.realPointer = `ERROR: ${e.message}`;
  }
}

async function main() {
  const browser = await chromium.launch();
  const results = {};
  for (const c of CANDIDATES) {
    const report = { url: c.url };
    const ctx = await browser.newContext({ viewport: { width: 1540, height: 900 }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    page.on("pageerror", (e) => (report.pageError = e.message));
    try {
      await page.goto(c.url, { waitUntil: "networkidle" });
      await waitReady(page);
      // stash the predecessor-finish ISO for the scripted snap step
      await page.evaluate(async () => {
        const a = await fetch("anchors.json").then((r) => r.json());
        window.__SPIKE_PREDFINISH = a.predecessor_finish.finish;
      });
      report.driveable = true;
      await driveScripted(page, c.id, report);
      await driveRealPointer(page, c.id, report);
    } catch (e) {
      report.driveable = false;
      report.error = e.message;
    }
    results[c.id] = report;
    await ctx.close();
  }
  await browser.close();
  console.log(JSON.stringify(results, null, 2));
}

main().catch((e) => { console.error(e); process.exit(1); });
