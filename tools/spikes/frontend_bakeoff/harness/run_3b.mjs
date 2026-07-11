// Session 3.0b harness — stress-tests vis-timeline (candidate_b_3b) against the
// four drop-ruling criteria. Evidence-grade: screenshots + machine-checked
// numbers, incl. a 20-run headless-reliability count. Throwaway spike infra.
//
//   node harness/run_3b.mjs [baseURL]
//   env SHOTS_DIR (default ./shots), RUNS (default 20 for C4)
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, resolve } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const BASE = process.argv[2] || "http://localhost:5173";
const URL = `${BASE}/candidate_b_3b.html`;
const SHOTS = process.env.SHOTS_DIR || resolve(__dirname, "..", "shots");
const RUNS = parseInt(process.env.RUNS || "20", 10);
mkdirSync(SHOTS, { recursive: true });

const shot = (page, name) => page.screenshot({ path: resolve(SHOTS, `${name}.png`) });
const state = (page) => page.evaluate(() => window.__spike.getState());

async function waitReady(page) {
  await page.waitForFunction(() => window.__spike && window.__spike.ready === true, { timeout: 15000 });
}

// DOM geometry helpers (read vis's own layout, page-side).
async function grabBox(page) {
  return page.evaluate(() => {
    const el = document.querySelector(".grabitem");
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width, h: r.height };
  });
}
async function groupCenterY(page, rowIndex) {
  return page.evaluate((i) => {
    const els = document.querySelectorAll(".vis-foreground .vis-group");
    const el = els[i]; if (!el) return null;
    const r = el.getBoundingClientRect();
    return r.top + r.height / 2;
  }, rowIndex);
}

// ---------------------------------------------------------------- C1 overlay
async function testC1(page, R) {
  await page.evaluate(() => window.__spike.reset());
  await page.evaluate(() => window.__spike.grab());
  await page.waitForTimeout(120);
  await shot(page, "b3b_c1_1_grab_overlay");           // labels legible at default zoom
  const p0 = await page.evaluate(() => window.__spike.overlayProbe());
  // zoom into a 30h window over the ghost region, then pan.
  await page.evaluate(() => window.__spike.zoomTo("2026-01-06T18:00:00Z", "2026-01-07T18:00:00Z"));
  await page.waitForTimeout(120);
  await shot(page, "b3b_c1_2_zoomed");
  const p1 = await page.evaluate(() => window.__spike.overlayProbe());
  await page.evaluate(() => window.__spike.zoomTo("2026-01-06T22:00:00Z", "2026-01-07T14:00:00Z"));
  await page.waitForTimeout(120);
  await shot(page, "b3b_c1_3_zoomed_more");
  const p2 = await page.evaluate(() => window.__spike.overlayProbe());
  // restore + reset
  await page.evaluate(() => window.__spike.zoomTo("2026-01-05T00:00:00Z", "2026-01-09T00:00:00Z"));
  await page.evaluate(() => window.__spike.reset());

  const probes = [p0, p1, p2];
  const allLegible = probes.every((p) => p.ghosts.every((g) => g.legible));
  const drifts = probes.flatMap((p) => p.ghosts.map((g) => g.driftPx).filter((d) => d != null));
  const maxDrift = drifts.length ? Math.max(...drifts) : null;
  R.C1 = {
    allLegible,
    maxDriftPx: maxDrift,
    driftThresholdPx: 6,
    pass: allLegible && maxDrift != null && maxDrift <= 6,
    probes: probes.map((p) => ({ window: p.window, ghosts: p.ghosts })),
  };
}

// -------------------------------------------------------- C2 mid-drag reject
async function testC2(page, R) {
  const DIM_ROW = 2;   // F001-RES005 — different facility, proven illegal
  await page.evaluate(() => window.__spike.reset());
  await page.evaluate(() => window.__spike.grab());
  await page.waitForTimeout(60);

  // --- scripted refusal ---
  const res = await page.evaluate((r) => window.__spike.moveToRow(r), DIM_ROW);
  await page.waitForTimeout(60);
  const sRefused = await state(page);
  await shot(page, "b3b_c2_1_refused_scripted");
  const dropped = await page.evaluate(() => { window.__spike.drop(); return window.__spike.getState(); });
  await page.waitForTimeout(60);
  await shot(page, "b3b_c2_2_returned_home");

  // --- real-pointer refusal: drag the bar UP into a dim row ---
  await page.evaluate(() => window.__spike.reset());
  const gb = await grabBox(page);
  const dimY = await groupCenterY(page, DIM_ROW);
  let realRefused = null, realHome = null, realErr = null;
  try {
    await page.mouse.move(gb.x, gb.y);
    await page.mouse.down();
    // diagonal, group-crossing gesture to engage Hammer, ending over the dim row
    await page.mouse.move(gb.x + 30, gb.y - 20, { steps: 5 });
    await page.mouse.move(gb.x + 60, dimY, { steps: 10 });
    await page.waitForTimeout(60);
    const mid = await state(page);
    realRefused = mid.refused === true;
    await shot(page, "b3b_c2_3_realdrag_over_dim");
    await page.mouse.up();
    await page.waitForTimeout(60);
    const after = await state(page);
    realHome = after.phase === "returned_home" && after.committed && after.committed.row === 12;
    await shot(page, "b3b_c2_4_realdrag_home");
  } catch (e) { realErr = e.message; }
  await page.evaluate(() => window.__spike.reset());

  R.C2 = {
    scriptedRefusedMidDrag: res.refused === true && sRefused.refused === true,
    scriptedReturnedHomeOnDrop: dropped.phase === "returned_home" && dropped.committed.row === 12,
    realRefusedMidDrag: realRefused,
    realReturnedHome: realHome,
    realErr,
    pass: res.refused === true && dropped.phase === "returned_home" && realRefused === true && realHome === true,
  };
}

// ------------------------------------------------------------- C3 magnet feel
async function testC3(page, R) {
  await page.evaluate(() => window.__spike.reset());
  await page.evaluate(() => window.__spike.grab());
  await page.waitForTimeout(40);
  // ONE real magnet: the shift-start / ghost anchor at 2026-01-07T07:00Z.
  // Measure falloff to THAT anchor specifically (isolated — not nearest-of-all),
  // which is the honest "one real magnet" question. (The 3.0b-first attempt
  // measured nearest-of-all-targets and a crowded field looked non-monotonic;
  // that was a probe artifact, corrected here.)
  const GHOST_ROW = 10;
  const anchor = "2026-01-07T07:00:00Z";
  const anchorMs = Date.parse(anchor);
  const samples = [];
  for (const offsetMin of [45, 30, 22, 15, 8, 3, 0]) {  // outside tol -> on anchor
    const t = new Date(anchorMs + offsetMin * 60000).toISOString();
    const iso = await page.evaluate(([iso, row]) => { window.__spike.moveToTime(iso, { row }); return iso; }, [t, GHOST_ROW]);
    const m = await page.evaluate(([raw, a]) => window.__spike.magnetTo(raw, a), [iso, anchor]);
    samples.push({ offsetMin, dMin: m.d_min, magnetStrength: m.strength, inTol: m.inTolerance });
  }
  await page.waitForTimeout(40);
  await shot(page, "b3b_c3_1_magnet_falloff");
  // Alt disables snap
  await page.evaluate(() => window.__spike.moveToTime("2026-01-07T07:03:00Z", { row: 10, alt: true }));
  const altState = await state(page);
  await shot(page, "b3b_c3_2_alt_free");

  // Real-pointer drag: does vis THROTTLE onMoving, or fire per pointer-move?
  // We count onMoving calls against the number of steps we emit; ratio ~1 means
  // the hook is NOT the bottleneck (granularity == input rate). Absolute Hz here
  // is governed by Playwright's synthetic pacing, so we report it only as color.
  await page.evaluate(() => window.__spike.reset());
  const gb = await grabBox(page);
  let calls = null, durMs = null, steps = 44, ratio = null, hz = null;
  try {
    await page.mouse.move(gb.x, gb.y);
    await page.mouse.down();
    await page.mouse.move(gb.x + 20, gb.y + 25, { steps: 4 });     // engage (4 steps)
    const t0 = Date.now();
    await page.mouse.move(gb.x + 220, gb.y + 30, { steps: 40 });   // sweep (40 steps)
    durMs = Date.now() - t0;
    await page.mouse.up();
    const st = await state(page);
    calls = st.onMovingCount;
    ratio = calls != null ? +(calls / steps).toFixed(2) : null;    // ~1 == no throttle
    hz = calls != null && durMs ? +((calls / durMs) * 1000).toFixed(1) : null;
  } catch (e) { R.C3_err = e.message; }
  await page.evaluate(() => window.__spike.reset());

  const strengths = samples.map((s) => s.magnetStrength);
  const monotonic = strengths.every((v, i) => i === 0 || v >= strengths[i - 1] - 0.001);
  const onTarget = samples[samples.length - 1].magnetStrength;
  const outsideZero = samples[0].magnetStrength === 0;    // 45min offset must be 0 (outside 30min tol)
  const noThrottle = ratio != null && ratio >= 0.8;       // vis fires ~per-event
  R.C3 = {
    anchor, samples,
    falloffMonotonic: monotonic,
    onTargetStrength: onTarget,
    zeroOutsideTolerance: outsideZero,
    altDisablesSnap: altState.tentative?.snappedTo === "free",
    onMovingCalls: calls, stepsEmitted: steps, callToStepRatio: ratio, noThrottle,
    onMovingHz_syntheticPacing: hz,
    // "supports falloff" = clean monotonic pull to full on the anchor, 0 outside
    // tolerance, Alt frees, and vis does NOT throttle the hook (ratio ~1).
    pass: monotonic && onTarget > 0.95 && outsideZero && altState.tentative?.snappedTo === "free" && noThrottle,
  };
}

// -------------------------------------------- C4 headless reliability (N runs)
async function oneRealDrag(page) {
  await page.evaluate(() => window.__spike.reset());
  const gb = await grabBox(page);
  if (!gb) return { ok: false, why: "no grab element" };
  // the diagonal, group-crossing gesture the 3.0 spike found necessary for Hammer.
  // grab is row 12; drag DOWN-right into rows 13/14 (legal amber) — a valid move.
  const downY = await groupCenterY(page, 14);
  try {
    await page.mouse.move(gb.x, gb.y);
    await page.mouse.down();
    await page.mouse.move(gb.x + 30, gb.y + 18, { steps: 5 });
    await page.mouse.move(gb.x + 90, downY, { steps: 10 });
    await page.waitForTimeout(30);
    const mid = await state(page);
    await page.mouse.up();
    await page.waitForTimeout(20);
    const after = await state(page);
    const engaged = mid.phase === "grabbing" && mid.onMovingCount > 0;
    const committedMove = after.phase === "dropped" || after.phase === "returned_home";
    return { ok: engaged && committedMove, engaged, phaseMid: mid.phase, calls: mid.onMovingCount, phaseAfter: after.phase };
  } catch (e) {
    return { ok: false, why: e.message };
  }
}

async function testC4(page, R) {
  const runs = [];
  for (let i = 0; i < RUNS; i++) runs.push(await oneRealDrag(page));
  const ok = runs.filter((r) => r.ok).length;
  R.C4 = {
    runs: RUNS, successes: ok, failures: RUNS - ok,
    successRate: `${ok}/${RUNS}`,
    pass: ok === RUNS,           // ruling: any flake = fragile = fail
    detail: runs,
  };
}

async function main() {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1540, height: 900 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  const R = { url: URL, ts: new Date().toISOString() };
  page.on("pageerror", (e) => (R.pageError = e.message));
  try {
    await page.goto(URL, { waitUntil: "networkidle" });
    await waitReady(page);
    await shot(page, "b3b_0_idle");
    await testC1(page, R);
    await testC2(page, R);
    await testC3(page, R);
    await testC4(page, R);
  } catch (e) {
    R.fatal = e.message;
  }
  R.verdict = {
    C1: R.C1?.pass, C2: R.C2?.pass, C3: R.C3?.pass, C4: R.C4?.pass,
    allFourPass: !!(R.C1?.pass && R.C2?.pass && R.C3?.pass && R.C4?.pass),
    rule: "vis-timeline adopted only if all four pass clean; any failure -> Candidate A",
  };
  writeFileSync(resolve(SHOTS, "report_3b.json"), JSON.stringify(R, null, 2));
  console.log(JSON.stringify(R.verdict, null, 2));
  console.log("C1", JSON.stringify(R.C1 && { pass: R.C1.pass, allLegible: R.C1.allLegible, maxDriftPx: R.C1.maxDriftPx }));
  console.log("C2", JSON.stringify(R.C2 && { pass: R.C2.pass, ...R.C2, detail: undefined }));
  console.log("C3", JSON.stringify(R.C3 && { pass: R.C3.pass, falloffMonotonic: R.C3.falloffMonotonic, onTargetStrength: R.C3.onTargetStrength, altDisablesSnap: R.C3.altDisablesSnap, onMovingHz: R.C3.onMovingHz }));
  console.log("C4", JSON.stringify(R.C4 && { pass: R.C4.pass, successRate: R.C4.successRate }));
  if (R.pageError) console.log("PAGEERROR:", R.pageError);
  if (R.fatal) console.log("FATAL:", R.fatal);
  await ctx.close();
  await browser.close();
}
main().catch((e) => { console.error(e); process.exit(1); });
