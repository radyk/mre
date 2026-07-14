// Cockpit screenshot harness (docs/07 Phase 3, CU5) — promoted from the 3.0b
// bake-off spike into production test infra. Drives the read-only cockpit
// through its scripted states against the hermetic multi_route fixture,
// captures a screenshot of each, and asserts machine-checked numbers:
//
//   * load           — board renders 6 lanes, bars, top strip grade
//   * select         — clicking a bar scopes the deictic ask (shared selection)
//   * ask+highlight  — THE acceptance moment: the answer cites the alternatives'
//                      PRICES and the cited bars + lanes light up in sync
//   * C1 drift       — standing regression: overlay tag vs vis-rendered bar
//                      center = 0.0px (a vis-timeline version bump trips this)
//   * mid-pan frame  — the 3.0b residual closed: drift holds DURING a pan
//   * registers      — testimony vs judgment render visibly distinct
//
// Screenshots land in tests/cockpit/shots/. Headless in CI.
import { test, expect } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const SHOTS = resolve(dirname(fileURLToPath(import.meta.url)), "shots");
mkdirSync(SHOTS, { recursive: true });
const shot = (page, name) => page.screenshot({ path: resolve(SHOTS, `${name}.png`) });

const SCHEDULE = "sched-multi-route-fixture";
const ACCEPTANCE_Q = "why is ORD-000012 on F001-RES001?";
const JUDGMENT_Q = "what data problems exist?";
const DRIFT_MAX_PX = 1.0;      // 0.0 expected; allow sub-pixel rounding

async function boot(page, extra = "") {
  await page.goto(`/?schedule=${SCHEDULE}${extra}`);
  await page.waitForFunction(() => window.__cockpit && window.__cockpit.ready === true, { timeout: 20000 });
  const err = await page.evaluate(() => window.__cockpit.error || null);
  expect(err, "cockpit booted without error").toBeNull();
  // readiness-wait for the cold-run first-paint race (the 0-bars flake from
  // 3.1c): the vis item DOM can lag window.__cockpit.ready by a frame. Retry
  // until at least one bar is painted before any test touches the board —
  // cheap insurance, one guard.
  await page.waitForFunction(
    () => document.querySelectorAll(".vis-item.bar").length > 0,
    { timeout: 10000 });
}

test("load — board renders lanes, bars, and the certificate grade", async ({ page }) => {
  await boot(page);
  // 6 resource lanes rendered as vis groups
  const lanes = await page.locator(".vis-labelset .vis-label").count();
  expect(lanes).toBeGreaterThanOrEqual(6);
  // assignment bars rendered
  const bars = await page.locator(".vis-item.bar").count();
  expect(bars).toBeGreaterThan(0);
  // planner vocabulary on screen, not UUIDs
  await expect(page.locator(".vis-labelset")).toContainText("F001-RES001");
  // top strip: contract version + certificate grade
  await expect(page.locator(".topstrip .ver")).toContainText("contract 1.3");
  await expect(page.locator(".topstrip .grade")).toContainText("ACCEPTED");
  await shot(page, "01_load");
});

test("interaction — Tier-0 payload loads in the background, enabling affordances", async ({ page }) => {
  await boot(page);
  // R-T1d: the split-endpoint payload is fetched AFTER first paint and drag
  // affordances (a stub flag in interim-A) enable on arrival. The board is
  // already interactive read-only before this resolves.
  await page.waitForFunction(() => window.__cockpit.interactionReady === true, { timeout: 10000 });
  const state = await page.evaluate(() => ({
    dragEnabled: window.__cockpit.dragEnabled,
    ops: window.__cockpit.interaction?.operations?.length || 0,
    hostAttr: document.getElementById("tl")?.getAttribute("data-drag-enabled"),
  }));
  expect(state.dragEnabled, "drag affordances enabled when the payload arrived").toBe(true);
  expect(state.ops, "interaction payload carries per-op Tier-0 facts").toBeGreaterThan(0);
  expect(state.hostAttr).toBe("true");
});

test("select — clicking a bar scopes the deictic ask (shared selection)", async ({ page }) => {
  await boot(page);
  await page.locator(".vis-item.bar").first().click();
  await expect(page.locator("#ask-scope")).toContainText("selected");
  // the deictic button is now enabled
  await expect(page.locator("#ask-deictic")).toBeEnabled();
  const selected = await page.locator(".vis-item.bar.selected").count();
  expect(selected).toBe(1);
  await shot(page, "02_select");
});

test("deictic — 'Why is this here?' injects the selection, not a literal 'this' (CU3)", async ({ page }) => {
  await boot(page);
  // With no selection the deictic button is inert and carries a hint, never a
  // dead control that fires a bare "why is this here?" at the router.
  await expect(page.locator("#ask-deictic")).toBeDisabled();
  await expect(page.locator("#ask-scope .scope-hint")).toBeVisible();

  // Select ORD-000012 on F001-RES001 (the bar with a canned answer). The
  // selection populates the shared scope; the deictic compiles the RESOLVED
  // planner-vocabulary question before /ask is ever called.
  await page.evaluate(() => {
    const doc = window.__cockpit.doc;
    const nameOf = (rid) => (doc.resources.find((r) => r.resource_id === rid) || {}).external_name;
    const a = doc.assignments.find(
      (x) => (x.work_orders || []).includes("ORD-000012") && nameOf(x.resource_id) === "F001-RES001");
    window.__cockpit.select(a.operation_ref);
  });
  await expect(page.locator("#ask-scope")).toContainText("ORD-000012");
  await expect(page.locator("#ask-scope")).toContainText("F001-RES001");
  await expect(page.locator("#ask-deictic")).toBeEnabled();

  await page.locator("#ask-deictic").click();

  // the RESOLVED question was sent — external refs, no literal "this"
  await expect(page.locator("#ask-log .msg.you pre").last())
    .toHaveText("why is ORD-000012 on F001-RES001?");
  // …and a non-fallback answer rendered (real testimony, not "can't answer")
  const answer = page.locator(".msg.answer").last();
  await expect(answer).toContainText("Evidence chain");
  await expect(answer).not.toContainText("can't answer");
  await shot(page, "07_deictic");
});

test("ask+highlight — the acceptance moment: priced answer, cited bars light up", async ({ page }) => {
  await boot(page);
  await page.evaluate((q) => window.__cockpit.ask(q), ACCEPTANCE_Q);
  await expect(page.locator(".msg.answer")).toBeVisible();

  // register: testimony, rendered distinctly
  const answer = page.locator(".msg.answer").last();
  await expect(answer).toHaveClass(/testimony/);

  // HONESTY ARMOR: the answer cites the ALTERNATIVES' PRICES from existing
  // evidence (no new answer path). If this ever fails, the gap is real.
  const text = await answer.locator("pre").innerText();
  expect(text, "answer names an alternative resource").toMatch(/F001-RES00\d/);
  expect(text, "answer prices the alternative").toMatch(/cost|Same cost/i);
  expect(text).toMatch(/Would cost [+-]?\$?\d/);

  // cited bars + lanes lit in sync
  const probe = await page.evaluate(() => window.__cockpit.overlayProbe());
  expect(probe.cited.length, "at least the two ops of the order are cited").toBeGreaterThanOrEqual(2);
  expect(probe.cited.every((c) => c.legible), "every cited tag is legible").toBe(true);
  const litBars = await page.locator(".vis-item.bar.cited").count();
  expect(litBars).toBeGreaterThanOrEqual(2);
  const litLanes = await page.locator(".vis-item.vis-background.cited-lane").count();
  expect(litLanes, "chosen + alternative lanes glow").toBeGreaterThanOrEqual(2);

  // C1 drift: overlay tag vs vis-rendered bar center = ~0.0px
  const drifts = probe.cited.map((c) => c.driftPx).filter((d) => d != null);
  const maxDrift = Math.max(...drifts);
  expect(maxDrift, "cited-tag drift at default zoom").toBeLessThanOrEqual(DRIFT_MAX_PX);

  await shot(page, "03_ask_highlight");  // the first frame of the sixty-second script
});

test("C1 drift — standing regression across zoom (label-vs-bar 0.0px)", async ({ page }) => {
  await boot(page);
  await page.evaluate((q) => window.__cockpit.ask(q), ACCEPTANCE_Q);
  await expect(page.locator(".msg.answer")).toBeVisible();

  // Only ON-SCREEN cited bars carry a tag — a bar scrolled out of the window is
  // correctly culled (the 3.0b overlay culled off-screen ghosts too). The
  // regression asserts drift + legibility for the rendered ones, and that at
  // least one cited bar is actually on screen (so the check has teeth).
  const maxAt = async () => {
    const p = await page.evaluate(() => window.__cockpit.overlayProbe());
    const onscreen = p.cited.filter((c) => c.driftPx != null);
    const ds = onscreen.map((c) => c.driftPx);
    return {
      onscreen: onscreen.length,
      max: ds.length ? Math.max(...ds) : null,
      allLegible: onscreen.every((c) => c.legible),
      window: p.window,
    };
  };

  const atDefault = await maxAt();
  // zoom in hard, but on a window that still contains a cited bar (Jan 5–7).
  await page.evaluate(() => window.__cockpit.setWindow("2026-01-05T00:00:00Z", "2026-01-07T00:00:00Z"));
  await page.waitForTimeout(120);
  const zoomed = await maxAt();
  await shot(page, "04_c1_zoomed");

  for (const s of [atDefault, zoomed]) {
    expect(s.onscreen, `a cited bar is on screen ${JSON.stringify(s.window)}`).toBeGreaterThan(0);
    expect(s.allLegible, "on-screen cited tags legible at every zoom").toBe(true);
    expect(s.max, `drift ${JSON.stringify(s.window)}`).toBeLessThanOrEqual(DRIFT_MAX_PX);
  }
});

test("mid-pan frame — drift holds DURING a pan (3.0b residual closed)", async ({ page }) => {
  await boot(page);
  await page.evaluate((q) => window.__cockpit.ask(q), ACCEPTANCE_Q);
  await expect(page.locator(".msg.answer")).toBeVisible();

  // pan the window right by ~18h WITHOUT settling first, then probe the frame.
  const w0 = await page.evaluate(() => window.__cockpit.getWindow());
  const shifted = (iso, h) => new Date(Date.parse(iso) + h * 3600000).toISOString();
  await page.evaluate(([a, b]) => window.__cockpit.setWindow(a, b),
    [shifted(w0.start, 18), shifted(w0.end, 18)]);
  const probe = await page.evaluate(() => window.__cockpit.overlayProbe());
  await shot(page, "05_midpan");

  const drifts = probe.cited.map((c) => c.driftPx).filter((d) => d != null);
  expect(drifts.length, "cited tags still tracked mid-pan").toBeGreaterThan(0);
  expect(Math.max(...drifts), "drift mid-pan").toBeLessThanOrEqual(DRIFT_MAX_PX);
});

test("registers — testimony and judgment render visibly distinct", async ({ page }) => {
  await boot(page);
  await page.evaluate((q) => window.__cockpit.ask(q), ACCEPTANCE_Q);
  await page.evaluate((q) => window.__cockpit.ask(q), JUDGMENT_Q);
  await expect(page.locator(".msg.answer.testimony")).toHaveCount(1);
  await expect(page.locator(".msg.answer.judgment")).toHaveCount(1);

  // the two registers carry different left-border colors (never blend)
  const tBorder = await page.locator(".msg.answer.testimony").first().evaluate((el) => getComputedStyle(el).borderLeftColor);
  const jBorder = await page.locator(".msg.answer.judgment").first().evaluate((el) => getComputedStyle(el).borderLeftColor);
  expect(tBorder).not.toBe(jBorder);
  await shot(page, "06_registers");
});
