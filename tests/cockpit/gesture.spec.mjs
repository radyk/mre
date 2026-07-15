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
const ondemand = load("ondemand.json");         // session 3.3 CU1 fixture

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

test("dragging a bar sideways moves the bar, NOT the timeline window (3.2c)", async ({ page }) => {
  await boot(page);
  // This is the ONE test driven by REAL pointer events (not the programmatic
  // window.__cockpit.drag hooks) — the pan/drag conflict lives in vis's own
  // Hammer pan, which only the real event path exercises. A horizontal drag
  // over a bar must leave the timeline window bit-for-bit unchanged.
  const bar = page.locator(".vis-item.bar").first();
  await expect(bar).toBeVisible();
  const box = await bar.boundingBox();
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;

  const before = await page.evaluate(() => window.__cockpit.getWindow());
  await page.mouse.move(cx, cy);
  await page.mouse.down();
  // pan/zoom suppressed the instant the pointer lands on a bar
  expect(await page.evaluate(() => window.__cockpit.board.isPanZoomEnabled())).toBe(false);
  // drag well past the grab slop, horizontally, in steps (each a Hammer panmove)
  for (const dx of [20, 80, 160, 260, 360]) {
    await page.mouse.move(cx + dx, cy, { steps: 3 });
  }
  const during = await page.evaluate(() => window.__cockpit.getWindow());
  expect(during.start, "window start unchanged mid-drag").toBe(before.start);
  expect(during.end, "window end unchanged mid-drag").toBe(before.end);
  // the bar itself moved: a grab happened and the carry is off its incumbent
  const midPhase = await page.evaluate(() => window.__cockpit.drag.state().phase);
  expect(["dragging", "grabbed"]).toContain(midPhase);

  await page.mouse.up();
  // pan/zoom resumes the instant the drag ends; the drop didn't move the window
  expect(await page.evaluate(() => window.__cockpit.board.isPanZoomEnabled())).toBe(true);
  const after = await page.evaluate(() => window.__cockpit.getWindow());
  expect(after.start, "window start unchanged after drop").toBe(before.start);
  expect(after.end, "window end unchanged after drop").toBe(before.end);
  await shot(page, "g00_pan_suppressed");
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

test("Tier-0 shading clears on drop → tentative, stays cleared through verdict (CU1)", async ({ page }) => {
  await boot(page);
  const op = opFor("verdict");           // canned VERDICT → a real tentative window
  const inc = incumbent(op);
  // grab first: the wash is painted while asking "where can it go"
  await page.evaluate((op) => window.__cockpit.drag.grab(op), op);
  expect(await page.locator(".drag-shade .shade-row").count(),
    "shaded while grabbed").toBeGreaterThan(0);

  // drop WITHOUT awaiting so we observe the tentative phase (the sandbox
  // re-solve is still in flight): the drop answered "where", so the legality
  // wash + ghosts must already be gone, leaving only the tentative bar.
  const obs = await page.evaluate(([op, rid, start]) => {
    const p = window.__cockpit.drag.dropAt(op, rid, start);
    const atDrop = {
      phase: window.__cockpit.drag.state().phase,
      shade: document.querySelectorAll(".drag-shade .shade-row").length,
      ghosts: document.querySelectorAll(".drag-ghosts .ghost-bar").length,
    };
    return p.then(() => ({
      atDrop,
      after: {
        phase: window.__cockpit.drag.state().phase,
        shade: document.querySelectorAll(".drag-shade .shade-row").length,
        ghosts: document.querySelectorAll(".drag-ghosts .ghost-bar").length,
      },
    }));
  }, [op, inc.resource_id, inc.start]);

  expect(obs.atDrop.phase).toBe("tentative");
  expect(obs.atDrop.shade, "wash cleared the instant the bar is dropped").toBe(0);
  expect(obs.atDrop.ghosts, "ghosts cleared on drop").toBe(0);
  expect(obs.after.phase).toBe("verdict");
  expect(obs.after.shade, "no wash repaints through the verdict phase").toBe(0);
  expect(obs.after.ghosts).toBe(0);
  // only the tentative bar + the card remain (traces belong to the verdict)
  expect(await page.locator(".carry-bar.tentative").count()).toBe(1);
  await expect(page.locator(".delta-card")).toBeVisible();
  await shot(page, "g09_shade_cleared");

  // Discard from this state restores a fully clean idle board.
  await page.locator(".dc-discard").click();
  await page.waitForTimeout(100);
  const st = await page.evaluate(() => window.__cockpit.drag.state());
  expect(st.phase).toBe("idle");
  expect(await page.locator(".drag-shade .shade-row").count()).toBe(0);
  expect(await page.locator(".carry-bar").count()).toBe(0);
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
  // Tier-0 shading fully clears once idle — no wash persists on an idle board.
  expect(await page.locator(".drag-shade .shade-row").count()).toBe(0);
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
  // shading is part of "everything" — the idle board carries no leftover wash.
  expect(await page.locator(".drag-shade .shade-row").count()).toBe(0);
  await shot(page, "g08_post_discard");
});

// ---------------------------------------------------------------------------
// Session 3.3 — coverage + card explainability
// ---------------------------------------------------------------------------

test("ghost labels carry planner work orders (CU2)", async ({ page }) => {
  await boot(page);
  const op = priced[0].label.target_operation_ref;
  await page.evaluate((op) => window.__cockpit.drag.grab(op), op);
  // the placement now speaks external refs end-to-end: the ghost bar's title
  // names its work order + price (empty work_orders was the CU2 bug).
  const title = await page.locator(".drag-ghosts .ghost-bar").first().getAttribute("title");
  expect(title, "ghost names its work order").toMatch(/ORD-\d+/);
});

test("grab an UNCOVERED op → on-demand pricing → ghosts fade in (CU1)", async ({ page }) => {
  await boot(page);
  const op = ondemand.op_id;   // a multi-eligible op the precomputed batch missed
  // before the grab it has no ghosts — the silent-failure the coverage work fixes
  const before = await page.evaluate((op) => window.__cockpit.drag.ghostsFor(op).length, op);
  expect(before, "uncovered op starts with zero ghosts").toBe(0);

  // absence is never silent: the shimmer shows the INSTANT an uncovered op is
  // grabbed (captured synchronously — the poll can hide it within ms once the
  // in-process fixture server answers, so we read it before awaiting).
  const shown = await page.evaluate((op) => {
    window.__cockpit.drag.grab(op);
    const el = document.querySelector(".drag-pricing");
    return { visible: el && !el.classList.contains("hidden"), text: el?.textContent || "" };
  }, op);
  expect(shown.visible, "pricing shimmer shows on grab of an uncovered op").toBe(true);
  expect(shown.text).toContain("pricing");

  // the POST primes the op; the poll re-fetches /alternatives and the ghosts
  // fade in for the still-grabbed op (the second grab would be instant).
  await page.waitForFunction((op) => window.__cockpit.drag.ghostsFor(op).length > 0,
    op, { timeout: 8000 });
  const ghosts = await page.locator(".drag-ghosts .ghost-bar").count();
  expect(ghosts, "priced ghosts appear on demand").toBeGreaterThan(0);
  await expect(page.locator(".drag-pricing")).toBeHidden();
  await shot(page, "g10_ondemand");
});

test("drop onto a ghost → FULL moved-set from the member doc (CU4)", async ({ page }) => {
  await boot(page);
  const g = priced[0];                    // member_index 0 → member_0.json served
  const op = g.label.target_operation_ref;
  // expected: diff the ghost's own solved document against the incumbent.
  const memberDoc = load("member_0.json");
  const inc = Object.fromEntries(schedule.assignments.map(
    (a) => [a.operation_ref, [a.resource_id, a.chunks[0].start]]));
  let expected = 0;
  for (const a of memberDoc.assignments) {
    const o = inc[a.operation_ref];
    if (o && (o[0] !== a.resource_id || o[1] !== a.chunks[0].start)) expected += 1;
  }
  expect(expected, "the member doc displaces more than the dropped bar").toBeGreaterThan(1);

  const st = await page.evaluate(([op, rid, start]) =>
    window.__cockpit.drag.dropAt(op, rid, start).then(() => window.__cockpit.drag.state()),
    [op, g.label.placement.resource_id, g.label.placement.start]);
  expect(st.phase).toBe("verdict");
  // the dropped bar traces instantly; the FULL consequences load from the doc
  await page.waitForFunction((n) => window.__cockpit.drag.state().traces === n,
    expected, { timeout: 6000 });
  const traceBars = await page.locator(".drag-traces .trace-old").count();
  expect(traceBars, "every displaced op is traced, not just the drop").toBe(expected);
  await shot(page, "g11_ghost_consequences");
});

test("delta card shows a 'why' clause on a major move (CU3)", async ({ page }) => {
  await boot(page);
  const op = opFor("verdict");            // canned verdict carries a reasoned move
  const inc = incumbent(op);
  await page.evaluate(([op, rid, start]) =>
    window.__cockpit.drag.dropAt(op, rid, start).then(() => {}),
    [op, inc.resource_id, inc.start]);
  await expect(page.locator(".delta-card.verdict")).toBeVisible();
  // the major consequence names WHY — occupancy, in planner vocabulary.
  const why = page.locator(".delta-card .dc-why").first();
  await expect(why).toBeVisible();
  await expect(why).toContainText("blocked on");
  await shot(page, "g12_why");
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
