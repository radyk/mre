// Sliced-world (rolling-horizon) harness (docs/07 Session 4B.3a CU2). Drives the
// read-only cockpit against a REAL assembled contract-1.7 rolling document
// (tools/build_rolling_fixture.py: committed frozen front + active window + a
// populated beyond-horizon tray) and against an EMPTY-tray variant. Screenshot-
// asserts each CU2 state. Runs on BOTH data-themes (light + dark projects). No
// solver in the browser — the document is committed as a fixture.
import { test, expect } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const SHOTS = resolve(dirname(fileURLToPath(import.meta.url)), "shots");
mkdirSync(SHOTS, { recursive: true });
const theme = () => test.info().project.metadata?.theme || "light";
const shot = (page, name) => page.screenshot({ path: resolve(SHOTS, `${name}__${theme()}.png`) });

const ROLLING = "sched-rolling-fixture";
const EMPTY = "sched-rolling-empty";

async function boot(page, schedule) {
  await page.request.post("/__test__/reset").catch(() => {});
  await page.goto(`/?schedule=${schedule}&theme=${theme()}`);
  await page.waitForFunction(() => window.__cockpit && window.__cockpit.ready === true, { timeout: 20000 });
  expect(await page.evaluate(() => window.__cockpit.error || null), "booted clean").toBeNull();
  await page.waitForFunction(() => document.querySelectorAll(".vis-item.bar").length > 0, { timeout: 10000 });
}

// --- CU2(a)/(c): a MIXED committed / active-window board ------------------
test("CU2 — the board renders both committed (locked) and active-window bars", async ({ page }) => {
  await boot(page, ROLLING);
  const probe = await page.evaluate(() => window.__cockpit.board.rollingProbe());
  // the document is a rolling one, and carries both states.
  expect(probe.rolling, "rolling block present").not.toBeNull();
  expect(probe.states.committed, "committed bars").toBeGreaterThan(0);
  expect(probe.states.active_window, "active-window bars").toBeGreaterThan(0);
  // committed bars carry the distinct locked class on the board.
  const committedBars = await page.locator(".vis-item.bar.committed").count();
  expect(committedBars, "committed bars rendered with the locked class").toBeGreaterThan(0);
  expect(committedBars, "committed count matches the document").toBe(probe.states.committed);
  const activeBars = await page.locator(".vis-item.bar.active-window").count();
  expect(activeBars, "active-window bars rendered").toBeGreaterThan(0);
  // the legend names the sliced-world vocabulary.
  await expect(page.locator(".legend")).toContainText("committed");
  await expect(page.locator(".legend")).toContainText("frozen boundary");
  await shot(page, "r1_mixed_board");
});

// --- CU2(b): the frozen-front boundary marker -----------------------------
test("CU2 — a labeled frozen-front boundary marker sits at frozen_until", async ({ page }) => {
  await boot(page, ROLLING);
  const m = await page.evaluate(() => window.__cockpit.board.markerProbe());
  expect(m.frozen, "frozen boundary marker drawn").toBe(true);
  expect(m.frozenMs, "frozen boundary has a timestamp").not.toBeNull();
  // it matches the document's frozen_until.
  const frozenUntil = await page.evaluate(() => window.__cockpit.doc.rolling.frozen_until);
  expect(m.frozenMs, "marker is at the document's frozen_until").toBe(Date.parse(frozenUntil));
  // the marker carries its label.
  await expect(page.locator(".marker.frozen .marker-label")).toContainText("frozen");
  await shot(page, "r2_frozen_marker");
});

// --- CU2(d): a POPULATED beyond-horizon tray ------------------------------
test("CU2 — the beyond-horizon tray lists known future work with a count badge", async ({ page }) => {
  await boot(page, ROLLING);
  const tray = page.locator("#beyond-tray");
  await expect(tray, "the tray is docked").toBeVisible();
  const probe = await page.evaluate(() => window.__cockpit.tray.probe());
  expect(probe.count, "the tray is populated").toBeGreaterThan(0);
  expect(probe.empty, "not the empty state").toBe(false);
  // the count badge equals the document's beyond-horizon list length.
  const docCount = await page.evaluate(() => window.__cockpit.doc.rolling.beyond_horizon.length);
  expect(probe.count, "badge matches the document").toBe(docCount);
  expect(probe.names.length, "one row per tray item").toBe(docCount);
  // names are planner vocabulary (work orders), never a raw UUID.
  const trayText = await tray.innerText();
  expect(trayText, "no UUID in the tray").not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-/);
  await expect(tray).toContainText("Beyond the horizon");
  await shot(page, "r3_tray_populated");
});

// --- CU2(d): the EMPTY tray shows zero, never hidden ----------------------
test("CU2 — an empty tray shows zero, not hidden", async ({ page }) => {
  await boot(page, EMPTY);
  const tray = page.locator("#beyond-tray");
  await expect(tray, "the tray is still docked when empty").toBeVisible();
  const probe = await page.evaluate(() => window.__cockpit.tray.probe());
  expect(probe.count, "the badge reads zero").toBe(0);
  expect(probe.empty, "the empty state is shown").toBe(true);
  await expect(tray).toContainText("Nothing beyond the horizon");
  // the board still renders bars (the whole book fits the window).
  expect(await page.locator(".vis-item.bar").count()).toBeGreaterThan(0);
  await shot(page, "r4_tray_empty");
});

// --- guard: a rolling board still renders read-only (no gesture surface) --
test("CU2 — the rolling board is read-only (no editable bars)", async ({ page }) => {
  await boot(page, ROLLING);
  // committed bars are static/locked; the board is editable:false throughout.
  const editable = await page.evaluate(() =>
    window.__cockpit.board.items.get().some((i) => i.editable === true));
  expect(editable, "no bar is editable in this read-only session").toBe(false);
});
