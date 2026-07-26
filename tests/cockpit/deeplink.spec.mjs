// The deep-link + schedule-picker harness (hotfix session CU1/CU2). Drives the
// built cockpit against the hermetic fixture server and pins the defect the
// founder hit: an explicit ?schedule= that the app's own freshness resolution
// rewrote to a different, newer schedule before the board had settled.
//
// CU1 — the param wins: the pinned id loads, the URL is never rewritten, and an
//       id this data root does not have is an honest NAMED error with the
//       schedule list as the recovery (never a silent substitution).
// CU2 — the picker: the header identity chip opens the registry listing (newest
//       first, rolling vs monolithic tagged) and selecting one navigates.
//
// Runs on BOTH data-themes. The 4.4 auto-follow chain is asserted here too — the
// fix must not turn a no-param boot into a tab that never follows a resubmit.
import { test, expect } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const SHOTS = resolve(dirname(fileURLToPath(import.meta.url)), "shots");
mkdirSync(SHOTS, { recursive: true });
const theme = () => test.info().project.metadata?.theme || "light";
const shot = (page, name) => page.screenshot({ path: resolve(SHOTS, `${name}__${theme()}.png`) });

const BASE = "sched-multi-route-fixture";
const ROLLING = "sched-rolling-fixture";
// every committed fixture carries created_at 2026-01-05T09:41:00Z, so an
// injected row at 11:00 is STRICTLY newer than all of them.
const NEWER = "sched-injected-newer";
const NEWEST = "sched-injected-newest";

const urlParam = (page, key) => new URL(page.url()).searchParams.get(key);

async function reset(page) {
  await page.request.post("/__test__/reset").catch(() => {});
}
async function injectNewer(page, id, created_at) {
  await page.request.post("/__test__/add-schedule", {
    data: { id, base: "sched-multi-route-distinct", created_at },
  });
}
async function booted(page) {
  await page.waitForFunction(() => window.__cockpit && window.__cockpit.ready === true,
                             { timeout: 20000 });
}

// --- CU1: an explicit ?schedule= is authoritative -------------------------
test("CU1 — an explicit ?schedule= loads THAT schedule and the URL is unchanged", async ({ page }) => {
  await reset(page);
  // a strictly newer schedule exists in the data root — exactly the dev-loop
  // condition (every dev_cockpit.ps1 boot mints one) that used to yank the tab.
  await injectNewer(page, NEWER, "2026-01-05T11:00:00Z");

  await page.goto(`/?schedule=${BASE}&theme=${theme()}`);
  await booted(page);

  expect(await page.evaluate(() => window.__cockpit.error || null), "booted clean").toBeNull();
  expect(await page.evaluate(() => window.__cockpit.scheduleId),
         "the board is bound to the pinned id").toBe(BASE);
  expect(await page.evaluate(() => window.__cockpit.pinned),
         "the boot is pinned").toBe(true);
  expect(urlParam(page, "schedule"), "the URL param was NOT rewritten").toBe(BASE);
  await page.waitForFunction(() => document.querySelectorAll(".vis-item.bar").length > 0,
                             { timeout: 10000 });

  // the newer schedule is OFFERED, not taken: a dismissible banner, and the URL
  // still names the pinned id after the freshness check has run.
  await expect(page.locator("#newer-banner"), "the newer schedule is offered").toBeVisible();
  await page.evaluate(() => window.__cockpit.checkFreshness());
  await page.waitForTimeout(300);
  expect(urlParam(page, "schedule"), "still the pinned id after a re-check").toBe(BASE);
  expect(await page.evaluate(() => window.__cockpit.scheduleId)).toBe(BASE);
  await shot(page, "dl1_pinned_wins");
});

test("CU1 — a pinned deep link to an id this data root has no schedule for is an honest named error", async ({ page }) => {
  await reset(page);
  const fake = "rolling-deadbeef-000";
  await page.goto(`/?schedule=${fake}&theme=${theme()}`);
  await booted(page);

  const nf = page.locator("#schedule-not-found");
  await expect(nf, "the not-found floor is shown").toBeVisible();
  await expect(nf, "it NAMES the id it could not find").toContainText(fake);
  expect(await page.evaluate(() => window.__cockpit.notFound), "the id is reported").toBe(fake);
  expect(await page.evaluate(() => window.__cockpit.scheduleId),
         "nothing was substituted").toBeNull();
  // no board was rendered in its place, and the strip stops claiming to load.
  expect(await page.locator(".split").count(), "the board is not rendered").toBe(0);
  await expect(page.locator("#topstrip .status")).toHaveText("no schedule");
  // the URL still names what was asked for — never rewritten to a working id.
  expect(urlParam(page, "schedule"), "the URL is unchanged").toBe(fake);
  // the recovery is the schedule list.
  const rows = nf.locator(".sched-list .sl-row");
  expect(await rows.count(), "the registered schedules are offered as the recovery")
    .toBeGreaterThan(0);
  await shot(page, "dl2_not_found");

  // and picking one from the recovery navigates to it.
  await nf.locator(`.sl-row[data-schedule-id="${BASE}"]`).click();
  await page.waitForFunction((want) => window.__cockpit && window.__cockpit.scheduleId === want,
                             BASE, { timeout: 20000 });
  expect(urlParam(page, "schedule")).toBe(BASE);
});

// --- the 4.4 auto-follow chain must survive the fix ------------------------
test("CU1 — a boot with NO param still auto-follows a newer schedule, and keeps following", async ({ page }) => {
  await reset(page);
  await injectNewer(page, NEWER, "2026-01-05T11:00:00Z");

  await page.goto(`/?theme=${theme()}`);
  await booted(page);
  // the 4.4 CU2 behaviour: no param + no uncommitted state → follow the newest.
  await page.waitForFunction((want) => window.__cockpit && window.__cockpit.scheduleId === want,
                             NEWER, { timeout: 20000 });
  expect(urlParam(page, "schedule")).toBe(NEWER);
  await expect(page.locator("#followed-toast"), "the switch is confirmed").toBeVisible();
  // the landing carries an app-written param, which must NOT count as pinned —
  // otherwise a tab that followed once would never follow again.
  expect(await page.evaluate(() => window.__cockpit.pinned),
         "an auto-follow landing is not pinned").toBe(false);

  // a SECOND resubmit lands: the followed tab follows again (the chain holds).
  await injectNewer(page, NEWEST, "2026-01-05T12:00:00Z");
  await page.evaluate(() => window.__cockpit.checkFreshness());
  await page.waitForFunction((want) => window.__cockpit && window.__cockpit.scheduleId === want,
                             NEWEST, { timeout: 20000 });
  expect(urlParam(page, "schedule")).toBe(NEWEST);
});

// --- CU2: the picker on the header chip -----------------------------------
test("CU2 — the identity chip opens the schedule list, newest first, kinds tagged", async ({ page }) => {
  await reset(page);
  await injectNewer(page, NEWER, "2026-01-05T11:00:00Z");
  await page.goto(`/?schedule=${BASE}&theme=${theme()}`);
  await booted(page);

  await expect(page.locator("#sched-picker"), "closed until asked").toHaveCount(0);
  await page.locator("#sched-ident").click();
  const picker = page.locator("#sched-picker");
  await expect(picker, "the picker opens").toBeVisible();
  await expect(page.locator("#sched-ident")).toHaveAttribute("aria-expanded", "true");

  const rows = picker.locator(".sl-row");
  await expect(rows.first()).toBeVisible();
  expect(await rows.count(), "the whole listing is offered").toBeGreaterThan(1);
  // newest first: the injected 11:00 row leads the tied 09:41 fixtures.
  expect(await rows.first().getAttribute("data-schedule-id"),
         "newest first").toBe(NEWER);
  // rolling vs monolithic is tagged from the row itself.
  expect(await picker.locator(`.sl-row[data-schedule-id="${ROLLING}"]`).getAttribute("data-kind"))
    .toBe("rolling");
  expect(await picker.locator(`.sl-row[data-schedule-id="${BASE}"]`).getAttribute("data-kind"))
    .toBe("monolithic");
  // the bound version is marked, not hidden.
  const current = picker.locator(`.sl-row[data-schedule-id="${BASE}"]`);
  await expect(current).toHaveClass(/current/);
  await expect(current).toHaveAttribute("aria-selected", "true");
  // every row carries its clock.
  await expect(current.locator(".sl-when")).not.toBeEmpty();
  await shot(page, "dl3_picker_open");

  // Escape closes it and returns nothing.
  await page.keyboard.press("Escape");
  await expect(page.locator("#sched-picker")).toHaveCount(0);
  expect(urlParam(page, "schedule"), "closing changes nothing").toBe(BASE);
});

test("CU2 — selecting a schedule navigates and the URL becomes the chosen id", async ({ page }) => {
  await reset(page);
  await page.goto(`/?schedule=${BASE}&theme=${theme()}`);
  await booted(page);

  await page.locator("#sched-ident").click();
  await page.locator(`#sched-picker .sl-row[data-schedule-id="${ROLLING}"]`).click();

  await page.waitForFunction((want) => window.__cockpit && window.__cockpit.scheduleId === want,
                             ROLLING, { timeout: 20000 });
  expect(urlParam(page, "schedule"), "the URL names the chosen schedule").toBe(ROLLING);
  expect(urlParam(page, "theme"), "other params survive the navigation").toBe(theme());
  // the chosen document really rendered — the rolling fixture docks its tray.
  await expect(page.locator("#beyond-tray")).toBeVisible();
  await shot(page, "dl4_picked_rolling");
});
