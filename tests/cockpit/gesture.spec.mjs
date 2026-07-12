// Gesture-surface harness (3.2b) — drives the drag interaction layer through
// every CU state against the DISTINCT-rate fixture (realistic rates → the
// forced-alternative ghosts are real and priced), screenshots each, and asserts
// machine-checked numbers. It drives the SAME transitions a pointer would, via
// the programmatic window.__cockpit.drag hooks (grab/dragTo/drop/dropAt/
// discard) — the deterministic path the pointer handlers themselves call.
//
// States (per the brief): grab-shade · ghosts · mid-drag magnet · refusal ·
// tentative+verdict · flagged · return-home · traces · post-discard restore.
// Standing regressions: grab→shade latency (<100ms, the bake-off bar) and the
// ghost-label drift (the C1 discipline extended to ghosts).
import { test, expect } from "@playwright/test";
import { mkdirSync, readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SHOTS = resolve(HERE, "shots");
mkdirSync(SHOTS, { recursive: true });
const shot = (page, name) => page.screenshot({ path: resolve(SHOTS, `${name}.png`) });

const SCHEDULE = "sched-multi-route-distinct";
const DIST = resolve(HERE, "fixtures", "distinct");
const load = (n) => JSON.parse(readFileSync(resolve(DIST, n), "utf-8"));

const schedule = load("schedule.json");
const alternatives = load("alternatives.json");
const sandbox = load("sandbox.json");
const interaction = load("interaction.json").interaction;

const GRAB_TO_SHADE_MAX_MS = 100;   // the bake-off latency bar (CU1)
const DRIFT_MAX_PX = 1.0;

// incumbent placement (resource + start) of an op, from the main document.
function incumbent(opRef) {
  const a = schedule.assignments.find((x) => x.operation_ref === opRef);
  return a ? { resource_id: a.resource_id, start: a.chunks[0].start } : null;
}
const eligibleOf = (opRef) =>
  interaction.operations.find((o) => o.operation_ref === opRef)?.eligible_resource_ids || [];

// the priced ghosts (each a distinct target op) + the canned sandbox outcomes.
const priced = alternatives.members.filter((m) => m.verdict === "priced" && m.label.placement);
const byOp = sandbox.by_op;
const opFor = (outcome) => Object.keys(byOp).find((op) => byOp[op].outcome === outcome);

async function boot(page) {
  await page.goto(`/?schedule=${SCHEDULE}`);
  await page.waitForFunction(() => window.__cockpit && window.__cockpit.ready === true, { timeout: 20000 });
  const err = await page.evaluate(() => window.__cockpit.error || null);
  expect(err, "cockpit booted without error").toBeNull();
  await page.waitForFunction(() => document.querySelectorAll(".vis-item.bar").length > 0, { timeout: 10000 });
  // the gesture surface stands up after the background payload + ghosts arrive.
  await page.waitForFunction(() => window.__cockpit.drag && window.__cockpit.alternativesReady === true, { timeout: 10000 });
  const dragErr = await page.evaluate(() => window.__cockpit.dragError || null);
  expect(dragErr, "gesture controller built without error").toBeNull();
}

test("grab → Tier-0 shading, sub-100ms (CU1)", async ({ page }) => {
  await boot(page);
  const op = priced[0].label.target_operation_ref;
  const st = await page.evaluate((op) => {
    window.__cockpit.drag.grab(op);
    return window.__cockpit.drag.state();
  }, op);
  expect(st.phase).toBe("grabbed");
  // every resource row shaded; at least one green legal region + the eligible
  // machines distinguished from the capability-dim ones.
  const rows = await page.locator(".drag-shade .shade-row").count();
  expect(rows).toBe(schedule.resources.length);
  const green = await page.locator(".drag-shade .shade-seg.green").count();
  expect(green, "at least one legal green region painted").toBeGreaterThan(0);
  const capDim = await page.locator(".drag-shade .shade-row.capability").count();
  expect(capDim, "wrong-machine rows are capability-dim").toBeGreaterThan(0);
  // the standing latency regression: grab → shade under the bar.
  expect(st.grabToShadeMs, `grab→shade ${st.grabToShadeMs}ms`).toBeLessThan(GRAB_TO_SHADE_MAX_MS);
  await shot(page, "g01_grab_shade");
});

test("hover-over-dim shows the one-line reason (CU1, R-DP2)", async ({ page }) => {
  await boot(page);
  const op = priced[0].label.target_operation_ref;
  // a resource this op canNOT run on → capability refusal with a reason.
  const wrong = schedule.resources.map((r) => r.resource_id)
    .find((rid) => !eligibleOf(op).includes(rid));
  const st = await page.evaluate(([op, wrong]) => {
    const inc = window.__cockpit.doc.assignments.find((a) => a.operation_ref === op);
    window.__cockpit.drag.grab(op);
    window.__cockpit.drag.dragTo(wrong, Date.parse(inc.chunks[0].start));
    return window.__cockpit.drag.state();
  }, [op, wrong]);
  expect(st.target.legal).toBe(false);
  expect(st.target.reason).toBe("capability");
  await expect(page.locator(".drag-reason")).toBeVisible();
  await expect(page.locator(".drag-overlay.refusing")).toHaveCount(1);
  await shot(page, "g02_refusal");
});

test("ghosts render, priced + legible + tracking (CU2)", async ({ page }) => {
  await boot(page);
  const op = priced[0].label.target_operation_ref;
  await page.evaluate((op) => window.__cockpit.drag.grab(op), op);
  const bars = await page.locator(".drag-ghosts .ghost-bar").count();
  expect(bars, "the grabbed op's priced ghost is drawn").toBeGreaterThan(0);
  // the ghost wears its price and stays legible; label tracks its bar (drift ~0)
  const probe = await page.evaluate(() => window.__cockpit.drag.ghostDriftProbe());
  expect(probe.length).toBeGreaterThan(0);
  for (const g of probe) {
    expect(g.legible, "ghost label legible").toBe(true);
    expect(g.driftPx, "ghost-label drift").toBeLessThanOrEqual(DRIFT_MAX_PX);
  }
  await expect(page.locator(".ghost-tag").first()).toContainText("%");
  await shot(page, "g03_ghosts");
});

test("mid-drag magnet snaps to the ghost anchor (CU3, R-DP3)", async ({ page }) => {
  await boot(page);
  const g = priced[0];
  const op = g.label.target_operation_ref;
  const ghostMs = Date.parse(g.label.placement.start);
  // aim a few pixels off the ghost start; the magnet should click onto it.
  const st = await page.evaluate(([op, rid, ghostMs]) => {
    window.__cockpit.drag.grab(op);
    window.__cockpit.drag.dragTo(rid, ghostMs + 9 * 60000);   // 9 min off
    return window.__cockpit.drag.state();
  }, [op, g.label.placement.resource_id, ghostMs]);
  expect(st.target.anchor, "snapped to an anchor").toBeTruthy();
  expect(st.target.anchor.type).toBe("ghost");
  expect(st.target.time_ms).toBe(ghostMs);          // clicked exactly onto it
  expect(st.target.legal).toBe(true);
  await shot(page, "g04_magnet");
});

test("Alt disables snapping (CU3)", async ({ page }) => {
  await boot(page);
  const g = priced[0];
  const op = g.label.target_operation_ref;
  const off = Date.parse(g.label.placement.start) + 9 * 60000;
  const st = await page.evaluate(([op, rid, off]) => {
    window.__cockpit.drag.grab(op);
    window.__cockpit.drag.dragTo(rid, off, /*altKey*/ true);
    return window.__cockpit.drag.state();
  }, [op, g.label.placement.resource_id, off]);
  // with Alt held the raw candidate is kept (no click-to-anchor)
  expect(st.target.anchor).toBeNull();
});

test("drop onto a ghost → near-instant verdict card + traces (CU4/CU5)", async ({ page }) => {
  await boot(page);
  const g = priced[0];
  const op = g.label.target_operation_ref;
  const st = await page.evaluate(([op, rid, start]) =>
    window.__cockpit.drag.dropAt(op, rid, start).then(() => window.__cockpit.drag.state()),
    [op, g.label.placement.resource_id, g.label.placement.start]);
  expect(st.phase).toBe("verdict");
  expect(st.dropToVerdictMs, "ghost drop is near-instant").toBeLessThan(GRAB_TO_SHADE_MAX_MS);
  await expect(page.locator(".delta-card")).toBeVisible();
  await expect(page.locator(".delta-card .dc-outcome")).toBeVisible();
  // the moved-set is traced old→new (R-DP7): the dropped bar's own trace at least
  expect(st.traces).toBeGreaterThan(0);
  const traceBars = await page.locator(".drag-traces .trace-old").count();
  expect(traceBars).toBeGreaterThan(0);
  const tentative = await page.locator(".carry-bar.tentative").count();
  expect(tentative, "the tentative bar persists until discard").toBe(1);
  await shot(page, "g05_verdict_traces");
});

test("legal drop off a ghost → sandbox verdict via /sandbox (CU4)", async ({ page }) => {
  await boot(page);
  const op = opFor("verdict");           // canned VERDICT, keyed by op
  const inc = incumbent(op);             // incumbent spot is legal + not a ghost
  const st = await page.evaluate(([op, rid, start]) =>
    window.__cockpit.drag.dropAt(op, rid, start).then(() => window.__cockpit.drag.state()),
    [op, inc.resource_id, inc.start]);
  expect(st.phase).toBe("verdict");
  expect(st.result.outcome).toBe("verdict");
  await expect(page.locator(".delta-card.verdict")).toBeVisible();
});

test("flagged outcome → 'bound not proven' card (CU4, R-T1c outcome 2)", async ({ page }) => {
  await boot(page);
  const op = opFor("feasible_unproven");
  const inc = incumbent(op);
  const st = await page.evaluate(([op, rid, start]) =>
    window.__cockpit.drag.dropAt(op, rid, start).then(() => window.__cockpit.drag.state()),
    [op, inc.resource_id, inc.start]);
  expect(st.result.outcome).toBe("feasible_unproven");
  await expect(page.locator(".delta-card.feasible_unproven")).toBeVisible();
  await expect(page.locator(".dc-status")).toContainText("not proven");
  await shot(page, "g06_flagged");
});

test("no verdict → return home with reason (CU4, R-T1c outcome 3 / R-DP2)", async ({ page }) => {
  await boot(page);
  const op = opFor("no_verdict");
  const inc = incumbent(op);
  await page.evaluate(([op, rid, start]) =>
    window.__cockpit.drag.dropAt(op, rid, start).then(() => new Promise((r) => setTimeout(r, 350))),
    [op, inc.resource_id, inc.start]);
  await expect(page.locator(".delta-card.return-home")).toBeVisible();
  await expect(page.locator(".dc-reason")).toContainText("verify");
  // the bar returned home: the gesture is over (idle), overlays cleared.
  const phase = await page.evaluate(() => window.__cockpit.drag.state().phase);
  expect(phase).toBe("idle");
  await shot(page, "g07_return_home");
});

test("accept is stubbed disabled; discard restores everything (CU4/CU5, R-DP7)", async ({ page }) => {
  await boot(page);
  const g = priced[0];
  const op = g.label.target_operation_ref;
  await page.evaluate(([op, rid, start]) =>
    window.__cockpit.drag.dropAt(op, rid, start),
    [op, g.label.placement.resource_id, g.label.placement.start]);
  await expect(page.locator(".delta-card")).toBeVisible();
  // accept is disabled (no publish workflow — a dead-end accept would break R-DP7)
  await expect(page.locator(".dc-accept")).toBeDisabled();
  // discard restores: card hidden, overlays + traces cleared, phase idle
  await page.locator(".dc-discard").click();
  await page.waitForTimeout(100);
  const st = await page.evaluate(() => window.__cockpit.drag.state());
  expect(st.phase).toBe("idle");
  expect(st.traces).toBe(0);
  await expect(page.locator(".delta-card")).toBeHidden();
  expect(await page.locator(".drag-traces .trace-old").count()).toBe(0);
  expect(await page.locator(".carry-bar").count()).toBe(0);
  await shot(page, "g08_post_discard");
});

test("delta-card line → navigate to the traced bar (CU5, R-DP7c)", async ({ page }) => {
  await boot(page);
  const g = priced[0];
  const op = g.label.target_operation_ref;
  await page.evaluate(([op, rid, start]) =>
    window.__cockpit.drag.dropAt(op, rid, start),
    [op, g.label.placement.resource_id, g.label.placement.start]);
  const line = page.locator(".delta-card .dc-line").first();
  await expect(line).toBeVisible();
  await line.click();
  // clicking the line selects the op's bar on the board (deictic navigation)
  await expect(page.locator(".vis-item.bar.selected")).toHaveCount(1);
});
