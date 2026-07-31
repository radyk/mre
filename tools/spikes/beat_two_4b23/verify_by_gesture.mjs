// Session 4B.23 Item 6 -- VERIFY BY GESTURE, NOT BY CURL.
//
// Drives a REAL browser against the REAL cockpit dev server and the REAL API
// (not the hermetic fixture server) and reports, for each gesture, the request
// sequence exactly as a network tab would show it, plus what the planner sees.
//
// SUBSTITUTION, STATED: the founder's measurement was Chrome devtools. The
// Chrome extension is not connected in this environment, so this is Playwright
// Chromium instead. It is a real browser executing the real drag handler over
// HTTP; what it is not is the founder's own Chrome profile.
//
//   node tools/spikes/beat_two_4b23/verify_by_gesture.mjs [--api http://localhost:8000]
//                                                        [--app http://localhost:5175]
// Playwright lives in the cockpit harness's own node_modules (tests/cockpit),
// not at the repo root, and Node resolves from THIS file's directory — so the
// package is resolved explicitly rather than by walking up from here.
import { createRequire } from "node:module";
import { resolve, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
const HERE = dirname(fileURLToPath(import.meta.url));
const HARNESS = resolve(HERE, "../../../tests/cockpit");
const req = createRequire(pathToFileURL(resolve(HARNESS, "package.json")));
const pw = req("@playwright/test");
const chromium = pw.chromium || pw.default?.chromium;

const arg = (k, d) => {
  const i = process.argv.indexOf(k);
  return i >= 0 ? process.argv[i + 1] : d;
};
const APP = arg("--app", "http://localhost:5175");
const API = arg("--api", "http://localhost:8000");
const DENSE = "rolling-c9973708-865";
const PINNED = "rolling-c362baa4-1b0";

const api = async (path, body) => {
  const r = await fetch(API + path, body ? {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  } : undefined);
  return (await r.json()).data;
};

const startOf = (a) => (a.chunks?.[0]?.start) || a.phases?.setup?.start;

// The 4B.22a gesture: on the machine carrying the most movable bars, pin bar i
// onto bar i+1's occupied start. Chosen by the board, not authored.
function collision(doc) {
  const movable = (doc.assignments || []).filter(
    (a) => a.commitment_state === "active_window" && (a.chunks || []).length <= 1);
  const byMachine = {};
  for (const a of movable) (byMachine[a.external_name || a.resource_id] ||= []).push(a);
  const busiest = Object.keys(byMachine).sort((x, y) => byMachine[y].length - byMachine[x].length)[0];
  const bars = byMachine[busiest].sort((a, b) => Date.parse(startOf(a)) - Date.parse(startOf(b)));
  const i = Math.floor(bars.length / 2);
  return { machine: busiest, mover: bars[i], target: bars[i + 1] };
}

async function openBoard(browser, schedule) {
  const page = await browser.newPage({ viewport: { width: 1540, height: 900 } });
  const log = [];
  page.on("response", async (res) => {
    const u = new URL(res.url());
    if (!/^\/(schedules|runs|submissions)/.test(u.pathname)) return;
    log.push({ method: res.request().method(), path: u.pathname, status: res.status(),
               t: Date.now() });
  });
  await page.goto(`${APP}/?schedule=${schedule}`);
  await page.waitForFunction(() => window.__cockpit && window.__cockpit.ready === true,
                             { timeout: 120000 });
  // The gesture surface only stands up once the Tier-0 interaction payload AND
  // the alternatives fetch have landed — dropping before then is refused by the
  // legality library with no sandbox call at all, which looks exactly like the
  // defect under investigation and is not it.
  await page.waitForFunction(
    () => window.__cockpit.drag && window.__cockpit.alternativesReady === true,
    { timeout: 120000 });
  log.length = 0;   // drop the boot traffic; we report the GESTURE
  return { page, log };
}

// ZOOM THE BOARD TO THE GESTURE, as a planner does before dragging anything.
//
// This is not cosmetic. R-DP9's no-op tolerance is `grid_px * pxToMinutes(1)` —
// it scales with the VIEW. On the dense demo board's default ~30-day window one
// pixel is about half an hour, so the tolerance is ~240 minutes and the 4B.22a
// collision gesture (236 min) is swallowed as "already here": no card, no
// sandbox call, phase back to idle. Reported as its own finding; here the view
// is set to the day around the drop so the gesture is a gesture.
async function zoomTo(page, iso, days = 2) {
  await page.evaluate(([t, d]) => {
    const c = Date.parse(t);
    window.__cockpit.board.setWindow(
      new Date(c - d * 12 * 3600 * 1000).toISOString(),
      new Date(c + d * 12 * 3600 * 1000).toISOString());
  }, [iso, days]);
  await page.waitForTimeout(250);
}

function report(title, log, t0) {
  console.log(`\n  request sequence (name / method / status / t+s):`);
  const seen = new Map();
  for (const r of log) {
    const name = r.path.split("/").slice(2).join("/") || "schedules";
    const key = `${r.method} ${name}`;
    seen.set(key, (seen.get(key) || 0) + 1);
    console.log(`    ${name.padEnd(28)} ${r.method.padEnd(5)} ${r.status}   `
              + `+${((r.t - t0) / 1000).toFixed(2)}s`);
  }
  if (!log.length) console.log("    (none)");
  return seen;
}

async function planned(page) {
  const card = await page.locator(".delta-card").first();
  const visible = await card.isVisible().catch(() => false);
  const cls = visible ? await card.getAttribute("class") : null;
  const text = visible ? (await card.innerText()).replace(/\n+/g, " | ") : null;
  const st = await page.evaluate(() => window.__cockpit.drag.state());
  return { visible, cls, text, st };
}

async function gesture(browser, schedule, label, { pin, before } = {}) {
  const { page, log } = await openBoard(browser, schedule);
  if (before) await before(page);
  const doc = await api(`/schedules/${schedule}`);
  const g = pin || collision(doc);
  const mover = g.mover, target = g.target;
  const startIso = g.startIso || startOf(target);
  console.log(`\n${"=".repeat(72)}\n${label}`);
  console.log(`  board   ${schedule}  (${(doc.assignments || []).length} bars)`);
  console.log(`  drag    ${mover.work_orders} op${mover.op_seq}  on ${g.machine}`);
  console.log(`  from    ${startOf(mover)}`);
  console.log(`  onto    ${startIso}`
            + (target ? `  (occupied by ${target.work_orders} op${target.op_seq})` : ""));

  await zoomTo(page, startIso);
  const t0 = Date.now();
  await page.evaluate(([op, rid, s]) =>
    window.__cockpit.drag.dropAt(op, rid, s, true),
    [mover.operation_ref, mover.resource_id, startIso]).catch((e) => {
      console.log("  drop threw:", String(e).slice(0, 200));
    });
  await page.waitForTimeout(600);
  const seen = report(label, log, t0);
  const p = await planned(page);
  console.log(`\n  the planner sees:`);
  console.log(`    card visible : ${p.visible}   class: ${p.cls || "-"}`);
  console.log(`    card text    : ${p.text || "(nothing on screen)"}`);
  console.log(`    phase        : ${p.st.phase}   beatOne: ${p.st.beatOne}`);
  console.log(`    beat one     : ${JSON.stringify(p.st.feasibilityGhost)}`);
  if (p.st.result) console.log(`    beat two     : ${JSON.stringify(p.st.result)}`);
  if (p.st.failure) console.log(`    failure      : ${JSON.stringify(p.st.failure)}`);
  await page.close();
  return { seen, planner: p };
}

// An ILLEGAL drop: a start inside a CLOSED calendar window on the mover's own
// machine. Found from the Tier-0 payload the board already holds — a spot the
// legality library refuses — so the refusal is the product's, not the script's.
async function illegalTarget(page, opRef) {
  return page.evaluate((op) => {
    const d = window.__cockpit.drag;
    const t = d.tier0For(op);
    const row = (t.rows || []).find((r) => (r.legal_regions || []).length);
    if (!row) return null;
    const regions = row.legal_regions.map((r) => [Date.parse(r.start), Date.parse(r.end)])
      .sort((a, b) => a[0] - b[0]);
    // the gap between two open regions is closed time
    for (let i = 0; i + 1 < regions.length; i++) {
      const gapStart = regions[i][1], gapEnd = regions[i + 1][0];
      if (gapEnd - gapStart > 6 * 3600 * 1000) {
        return { resource_id: row.resource_id,
                 start: new Date(gapStart + (gapEnd - gapStart) / 2).toISOString() };
      }
    }
    return null;
  }, opRef);
}

(async () => {
  const browser = await chromium.launch();
  try {
    // (a) A LEGAL DROP on the dense board.
    await gesture(browser, DENSE, "(a) LEGAL DROP on the DENSE board (386 bars)");

    // (b) AN ILLEGAL DROP — into closed calendar.
    {
      const { page, log } = await openBoard(browser, DENSE);
      const doc = await api(`/schedules/${DENSE}`);
      const { mover, machine } = collision(doc);
      const bad = await illegalTarget(page, mover.operation_ref);
      console.log(`\n${"=".repeat(72)}\n(b) ILLEGAL DROP — into closed calendar`);
      console.log(`  drag    ${mover.work_orders} op${mover.op_seq} on ${machine}`);
      console.log(`  onto    ${bad ? bad.start : "(no closed gap found)"}`);
      if (bad) await zoomTo(page, bad.start);
      const t0 = Date.now();
      if (bad) {
        await page.evaluate(([op, rid, s]) =>
          window.__cockpit.drag.dropAt(op, rid, s, true), [mover.operation_ref, bad.resource_id, bad.start]);
      }
      await page.waitForTimeout(600);
      report("(b)", log, t0);
      const p = await planned(page);
      console.log(`\n  the planner sees:`);
      console.log(`    card visible : ${p.visible}   class: ${p.cls || "-"}`);
      console.log(`    reason tip   : ${await page.locator(".drag-reason").innerText().catch(() => "(none)")}`);
      console.log(`    phase        : ${p.st.phase}`);
      await page.close();
    }

    // (c) A DROP WHERE BEAT TWO IS MADE TO FAIL — the route is installed in the
    // BROWSER, so the failure is a real network failure the app must handle.
    await gesture(browser, DENSE, "(c) LEGAL DROP with BEAT TWO FORCED TO FAIL", {
      before: async (page) => {
        await page.route("**/sandbox", (route) => route.fulfill({
          status: 503, contentType: "application/json",
          body: JSON.stringify({ api_version: "1",
            error: { code: 503, message: "sandbox worker unavailable" } }),
        }));
      },
    });

    // (d) THE SAME LEGAL DROP on the pinned exam world — the regression target.
    await gesture(browser, PINNED, "(d) THE SAME LEGAL DROP on rolling-c362baa4-1b0 (56 bars)");
  } finally {
    await browser.close();
  }
})();
