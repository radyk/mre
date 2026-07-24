// Planner-surface harness (docs/07 Session 4.2). Drives the read-layer cockpit
// against the hand-authored planner fixture (closures / maintenance / overtime /
// setup / a split op / a standing pin / customers) and screenshot-asserts each
// CU state. Runs on BOTH data-themes (light + dark projects). The now-line and
// gap arithmetic is unit-tested in rowstats.spec.mjs (the JS port pinned to the
// Python eligibility fixtures); here we assert the surface renders it truthfully.
import { test, expect } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const SHOTS = resolve(dirname(fileURLToPath(import.meta.url)), "shots");
mkdirSync(SHOTS, { recursive: true });
const theme = () => test.info().project.metadata?.theme || "light";
const shot = (page, name) => page.screenshot({ path: resolve(SHOTS, `${name}__${theme()}.png`) });

const SCHEDULE = "sched-planner-fixture";

async function boot(page) {
  await page.request.post("/__test__/reset").catch(() => {});
  await page.goto(`/?schedule=${SCHEDULE}&theme=${theme()}`);
  await page.waitForFunction(() => window.__cockpit && window.__cockpit.ready === true, { timeout: 20000 });
  expect(await page.evaluate(() => window.__cockpit.error || null), "booted clean").toBeNull();
  await page.waitForFunction(() => document.querySelectorAll(".vis-item.bar").length > 0, { timeout: 10000 });
}

// --- CU1: capacity-state backgrounds + shift structure --------------------
test("CU1 — capacity bands: off-shift / closure / maintenance / overtime / open-idle", async ({ page }) => {
  await boot(page);
  const bands = await page.evaluate(() => window.__cockpit.board.capacityProbe());
  // every capacity state is present on the board (the fixture exercises all).
  expect(bands.offshift, "off-shift bands").toBeGreaterThan(0);
  expect(bands.maintenance, "planned-maintenance band").toBeGreaterThan(0);
  expect(bands.overtime, "overtime (premium) band").toBeGreaterThan(0);
  expect(bands.openidle, "open-idle band").toBeGreaterThan(0);
  // maintenance and closure are visually distinct classes (both hatched).
  expect(await page.locator(".vis-item.vis-background.cap-maintenance").count()).toBeGreaterThan(0);
  // the legend names the new capacity states.
  await expect(page.locator(".legend")).toContainText("maintenance");
  await expect(page.locator(".legend")).toContainText("overtime");
  await shot(page, "p1_capacity");
});

// --- CU2: time anchors ----------------------------------------------------
test("CU2 — the now-line sits at the reference date; due/release scope to a selection", async ({ page }) => {
  await boot(page);
  let m = await page.evaluate(() => window.__cockpit.board.markerProbe());
  // now-line is drawn at the run's reference date (not wall clock) and tracks vis.
  expect(m.nowMs, "now-line present").not.toBeNull();
  expect(m.nowDriftPx, "now-line tracks vis geometry").toBeLessThanOrEqual(1.0);
  expect(m.ticks, "shift-boundary ticks drawn").toBeGreaterThan(0);
  // no order scoped yet → no due/release markers.
  expect(m.due).toBe(false);

  // select the late split order → its due marker appears.
  await page.evaluate(() => {
    const doc = window.__cockpit.doc;
    const a = doc.assignments.find((x) => (x.work_orders || []).includes("ORD-102"));
    window.__cockpit.board.select(a.operation_ref);
  });
  m = await page.evaluate(() => window.__cockpit.board.markerProbe());
  expect(m.due, "due marker after selection").toBe(true);
  await shot(page, "p2_anchors");
});

// --- CU3: hover cards -----------------------------------------------------
test("CU3 — job card carries planner vocabulary; downtime card names the closure", async ({ page }) => {
  await boot(page);
  // job card for the standing-pinned order (a-101 = ORD-101, Globex, tight).
  const shown = await page.evaluate(() => window.__cockpit.board.hoverCards._showJob("a-101"));
  expect(shown).toBe(true);
  const card = page.locator(".hover-card.job");
  await expect(card).toBeVisible();
  await expect(card).toContainText("ORD-101");
  await expect(card).toContainText("Globex Corp");
  await expect(card).toContainText("120 ea");
  await expect(card).toContainText("committed");     // standing-pin state
  // CU5a (Session 4A.3): the bar's span + its lateness/slack figure.
  await expect(card).toContainText("When");
  await expect(card).toContainText("Slack");
  await expect(card).toContainText("→");             // start → end span
  // never a UUID on the card.
  expect(await card.innerText()).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}/);
  await shot(page, "p3_jobcard");

  // downtime card over the planned-maintenance band on RES002.
  const kind = await page.evaluate(() => {
    const doc = window.__cockpit.doc;
    const rid = doc.resources.find((r) => r.external_name === "F001-RES002").resource_id;
    const t = Date.parse("2026-01-07T12:00:00Z");
    return window.__cockpit.board.hoverCards._showBand(rid, t);
  });
  expect(kind).toBe("maintenance");
  await expect(page.locator(".hover-card.downtime")).toContainText("Planned maintenance");
  await expect(page.locator(".hover-card.downtime")).toContainText("reopens");
});

// --- CU4: row intelligence ------------------------------------------------
test("CU4 — the row-label strip shows utilization + booked-through + next-gap", async ({ page }) => {
  await boot(page);
  const stats = await page.evaluate(() => window.__cockpit.board.rowStatsProbe("F001-RES001"));
  expect(stats, "row stats for RES001").not.toBeNull();
  expect(stats.util, "utilization computed").toBeGreaterThan(0);
  expect(stats.booked_through, "booked-through from the document").toBeTruthy();
  expect(stats.next_open_gap, "next-open-gap from the document").toBeTruthy();
  // the strip is rendered in the row label (a util % is on screen).
  await expect(page.locator(".row-strip .rs-util").first()).toContainText("%");
  await shot(page, "p4_rowstrip");
});

// --- CU5: operation anatomy ----------------------------------------------
test("CU5 — setup segment, split-op kinship, and the pin indicator family", async ({ page }) => {
  await boot(page);
  // setup segment: a-100 carries a --setup-frac inline var driving the leading hatch.
  const setupBars = await page.locator('.vis-item.bar[style*="setup-frac"]').count();
  expect(setupBars, "a bar renders a setup segment").toBeGreaterThan(0);
  // split op: ORD-102 renders as >=2 linked pieces + a kinship connector.
  const pieces = await page.locator(".vis-item.bar.chunk-piece").count();
  expect(pieces, "split op renders as pieces").toBeGreaterThanOrEqual(2);
  const links = await page.locator(".vis-item.vis-background.chunk-link").count();
  expect(links, "a kinship connector spans the pause").toBeGreaterThan(0);
  // the standing-pin (accepted commitment) marker is present.
  expect(await page.locator(".vis-item.bar.standing-pin").count()).toBeGreaterThan(0);
  await shot(page, "p5_anatomy");
});

// --- Session 4.3 CU4: marker + band legibility ----------------------------
test("CU4 — the due marker is decoupled from the late-alarm red and rendered dashed", async ({ page }) => {
  await boot(page);
  // token-level: the due marker hue is NOT the late-bar red (a met due date must
  // not read as a problem).
  const [markerDue, barLate] = await page.evaluate(() => [
    getComputedStyle(document.documentElement).getPropertyValue("--marker-due").trim(),
    getComputedStyle(document.documentElement).getPropertyValue("--bar-late").trim(),
  ]);
  expect(markerDue, "due hue decoupled from the late red").not.toBe(barLate);

  // scope a due marker, then assert it renders as an OUTLINE (dashed gradient),
  // not a solid alarm line.
  await page.evaluate(() => {
    const doc = window.__cockpit.doc;
    const a = doc.assignments.find((x) => (x.work_orders || []).includes("ORD-102"));
    window.__cockpit.board.select(a.operation_ref);
  });
  const dueImg = await page.locator(".marker.due").first().evaluate((el) => getComputedStyle(el).backgroundImage);
  expect(dueImg, "due marker is a dashed outline").toContain("gradient");
});

test("CU4 — marker labels stay full words near the right edge (no '…ase' clipping)", async ({ page }) => {
  await boot(page);
  const due = await page.evaluate(() => {
    const doc = window.__cockpit.doc;
    const a = doc.assignments.find((x) => (x.work_orders || []).includes("ORD-102"));
    window.__cockpit.board.select(a.operation_ref);
    const so = doc.service_outcomes.find((s) => s.work_order === "ORD-102");
    return so ? so.due : null;
  });
  expect(due, "ORD-102 carries a due date").not.toBeNull();
  // put the due date near the right edge of the window, where a naive label would
  // clip to a fragment.
  await page.evaluate((d) => {
    const t = Date.parse(d);
    window.__cockpit.setWindow(new Date(t - 20 * 3600000).toISOString(),
      new Date(t + 2 * 3600000).toISOString());
  }, due);
  await page.waitForTimeout(150);
  const info = await page.evaluate(() => {
    const lbl = document.querySelector(".marker.due .marker-label");
    const ov = document.querySelector(".marker-overlay");
    if (!lbl || !ov) return null;
    const l = lbl.getBoundingClientRect(), o = ov.getBoundingClientRect();
    return { text: lbl.textContent, flip: lbl.classList.contains("flip"),
      labelRight: l.right, ovRight: o.right };
  });
  expect(info, "the due marker + label are on screen near the right edge").not.toBeNull();
  expect(info.text, "the full word, not a fragment").toContain("due");
  expect(info.labelRight, "label not clipped past the board's right edge")
    .toBeLessThanOrEqual(info.ovRight + 1);
});

test("CU4 — a downtime band card states its window AND its reopen time", async ({ page }) => {
  await boot(page);
  await page.evaluate(() => {
    const doc = window.__cockpit.doc;
    const rid = doc.resources.find((r) => r.external_name === "F001-RES002").resource_id;
    window.__cockpit.board.hoverCards._showBand(rid, Date.parse("2026-01-07T12:00:00Z"));
  });
  const dt = page.locator(".hover-card.downtime");
  await expect(dt).toBeVisible();
  // the closed WINDOW itself, as a HH:MM – HH:MM span…
  expect(await dt.innerText(), "the card states the window span").toMatch(/\d{2}:\d{2}\s*–\s*\d{2}:\d{2}/);
  // …and when it lifts.
  await expect(dt).toContainText("reopens");
});
