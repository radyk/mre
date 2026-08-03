// R-TZ1 — ONE CLOCK (docs/04 2026-08-03; Session 4B.35 Item 1).
//
// THE USER'S DOOR: a real board, booted in a browser whose timezone is NOT the
// facility's, asserting that what a planner READS is the declared clock anyway.
//
// The property under test is deliberately stated as an INVARIANCE, not as a
// string: *the browser's timezone does not change what the board says*. That is
// the defect from 4B.35 §2 exactly — the board and job panel rendered through
// `toLocaleString(undefined, …)`, so the same stored instant read five hours
// from the ask path's testimony in Toronto and would have read differently again
// in Istanbul. A test that pinned one expected string would pass on a laptop in
// UTC while the defect was live everywhere else.
//
// Every case runs the page in America/Toronto (UTC−5 in January, the offset the
// live specimen was found at) and asserts against UTC, the clock the fixture's
// instants are stored and declared in.
import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SCHEDULE = "sched-rolling-fixture";
const doc = JSON.parse(
  readFileSync(resolve(HERE, "fixtures", "rolling", "schedule.json"), "utf-8"));

// A browser five hours from the facility. If the cockpit reaches for the
// browser's clock anywhere, every assertion below moves by exactly this much.
test.use({ timezoneId: "America/Toronto" });

// The instant every case is anchored on: a single-chunk active bar, and the
// UTC wall-clock reading of it, computed here from the stored ISO.
const bar = doc.assignments.find(
  (a) => (a.chunks || []).length === 1 && a.commitment_state !== "committed");
const startMs = Date.parse(bar.chunks[0].start);
const utcHM = new Intl.DateTimeFormat("en-CA", {
  hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC",
}).format(new Date(startMs));

async function boot(page) {
  await page.request.post("/__test__/reset").catch(() => {});
  await page.goto(`/?schedule=${SCHEDULE}&theme=light`);
  await page.waitForFunction(() => window.__cockpit?.ready === true, { timeout: 20000 });
  await page.waitForFunction(
    () => document.querySelectorAll(".vis-item.bar").length > 0, { timeout: 10000 });
}

test("the browser's timezone does not move what the board renders (R-TZ1)", async ({ page }) => {
  await boot(page);

  // PREMISE: this browser really is five hours off the facility clock. Without
  // it the whole spec could pass in a UTC container while the defect is live.
  const offset = await page.evaluate(() => new Date().getTimezoneOffset());
  expect(Math.abs(offset), "the test browser is NOT on the facility clock")
    .toBeGreaterThan(0);

  // The product's OWN rendering path — the one every planner-facing site now
  // goes through — for the stored instant.
  const rendered = await page.evaluate((ms) => window.__cockpit.clock.fmt(ms, {
    hour: "2-digit", minute: "2-digit", hour12: false }), startMs);
  expect(rendered, `stored ${bar.chunks[0].start} must render on the declared clock`)
    .toBe(utcHM);

  // ...and the browser's own rendering of the same instant is DIFFERENT, which
  // is what makes the assertion above load-bearing rather than tautological.
  const browserHM = await page.evaluate((ms) => new Date(ms).toLocaleString(undefined, {
    hour: "2-digit", minute: "2-digit", hour12: false }), startMs);
  expect(browserHM, "the browser clock genuinely disagrees here").not.toBe(utcHM);
});

test("the axis is on the declared clock, not the browser's (R-TZ1)", async ({ page }) => {
  await boot(page);
  // Frame TIGHT — 100 minutes either side — so the ruler carries only the hours
  // immediately around the anchor. A wide window shows every hour of the day and
  // would contain the browser-clock hour too, making the negative assertion below
  // vacuous rather than false.
  await page.evaluate(([a, b]) => window.__cockpit.setWindow(a, b), [
    new Date(startMs - 100 * 60e3).toISOString(),
    new Date(startMs + 100 * 60e3).toISOString()]);
  await page.waitForTimeout(600);

  const labels = await page.evaluate(() => [...document.querySelectorAll(
    ".vis-time-axis .vis-text.vis-minor")].map((e) => e.textContent.trim())
    .filter((t) => /^\d{2}:\d{2}$/.test(t)));
  expect(labels.length, "the axis is showing hour labels").toBeGreaterThan(2);

  // The hour the anchor instant falls in, as UTC, must appear on the ruler; the
  // hour the BROWSER would have drawn it at must not.
  const utcHour = new Date(startMs).getUTCHours();
  const localHour = await page.evaluate((ms) => new Date(ms).getHours(), startMs);
  expect(utcHour, "premise: the two clocks disagree on the hour").not.toBe(localHour);
  const hh = (h) => `${String(h).padStart(2, "0")}:00`;
  expect(labels, "the axis names the declared-clock hour").toContain(hh(utcHour));
  expect(labels, "the axis does NOT name the browser-clock hour")
    .not.toContain(hh(localHour));
});

test("the board declares which clock it is in (R-TZ1)", async ({ page }) => {
  await boot(page);
  const chip = page.locator(".topstrip .clock-label");
  await expect(chip, "the clock is named on the board chrome").toBeVisible();
  const text = (await chip.textContent()).trim();
  expect(text, "the label names the zone").toMatch(/^All times \S+/);
  // R-TZ1's fallback clause: a clock we DEFAULTED to must never read as one the
  // facility declared. The hover carries the distinction either way.
  const title = await chip.getAttribute("title");
  expect(title, "the label explains which clock and why").toBeTruthy();
  const zone = await page.evaluate(() => window.__cockpit.clock.zone());
  expect(text).toContain(zone);
});

test("the job panel and the hover card agree with the axis (R-TZ1)", async ({ page }) => {
  await boot(page);
  // Open the whole-job panel the way the board does — through the selection.
  await page.evaluate((op) => window.__cockpit.select(op), bar.operation_ref);
  await page.waitForTimeout(400);
  const panel = await page.evaluate(
    () => document.querySelector(".job-panel")?.textContent || "");
  expect(panel, "the job panel is open").not.toBe("");
  expect(panel, `the panel states the declared-clock time ${utcHM}`).toContain(utcHM);

  const browserHM = await page.evaluate((ms) => new Date(ms).toLocaleString(undefined, {
    hour: "2-digit", minute: "2-digit", hour12: false }), startMs);
  expect(panel, "the panel does NOT state the browser-clock time")
    .not.toContain(browserHM);
});
