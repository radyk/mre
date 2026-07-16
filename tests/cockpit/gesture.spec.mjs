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
  // Clear the fixture server's per-session version lifecycle (session 3.8): a
  // publish in a prior test supersedes its base, which would break a later boot
  // of that base id. Reset BEFORE navigation so the page's meta read is clean.
  await page.request.post("/__test__/reset").catch(() => {});
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

test("accept mints a new proposed version; publish supersedes it (CU1, R-DP7)", async ({ page }) => {
  await boot(page);
  const op = opFor("verdict");
  const inc = incumbent(op);
  // drop → verdict; Accept is a LIVE control now (no longer stubbed disabled)
  const v = await page.evaluate(([op, rid, start]) =>
    window.__cockpit.drag.dropAt(op, rid, start).then(() => window.__cockpit.drag.state()),
    [op, inc.resource_id, inc.start]);
  expect(v.phase).toBe("verdict");
  await expect(page.locator(".dc-accept")).toBeEnabled();

  // accept → a NEW proposed version; the board rebinds, the card reads Accepted,
  // the strip + hook follow the new version (R-DP7: the strip reflects state).
  const acc = await page.evaluate(() => window.__cockpit.drag.accept().then(() => ({
    state: window.__cockpit.drag.state(),
    changed: window.__cockpit.versionChanged,
    scheduleId: window.__cockpit.scheduleId,
  })));
  expect(acc.state.phase).toBe("accepted");
  expect(acc.state.acceptedId, "accept records the new version id").toBeTruthy();
  expect(acc.changed.status).toBe("proposed");
  expect(acc.scheduleId, "the cockpit retargets the new version").toBe(acc.state.acceptedId);
  await expect(page.locator(".delta-card.accepted")).toBeVisible();
  await expect(page.locator(".dc-publish")).toBeVisible();
  await shot(page, "g10_accepted");

  // publish → published; the prior version is superseded; the strip flips.
  const pub = await page.evaluate(() => window.__cockpit.drag.publish().then(() => ({
    state: window.__cockpit.drag.state(),
    changed: window.__cockpit.versionChanged,
  })));
  expect(pub.state.phase).toBe("published");
  expect(pub.changed.status).toBe("published");
  await expect(page.locator(".delta-card.published")).toBeVisible();
  await expect(page.locator("#topstrip .status")).toContainText("published");
  await shot(page, "g11_published");
});

// ---------------------------------------------------------------------------
// Session 3.8 — version-lifecycle continuity (the missing seam). One session
// drives TWO consecutive edit→accept cycles and one edit→accept→publish→edit
// cycle, asserting the bound id + URL advance each time and that an accepted bar
// stays where committed (never a superseded-id 409 → return-home).
// ---------------------------------------------------------------------------

// The schedule id the whole cockpit is bound to right now: the hook, the drag
// controller, and the address bar must all agree (CU1).
const boundIds = (page) => page.evaluate(() => ({
  hook: window.__cockpit.scheduleId,
  controller: window.__cockpit.drag.scheduleId(),
  url: new URLSearchParams(location.search).get("schedule"),
  status: window.__cockpit.versionChanged && window.__cockpit.versionChanged.status,
}));

// grab a ghost's op, drop onto its priced placement, accept → the new version.
async function editAccept(page, ghost) {
  const op = ghost.label.target_operation_ref;
  const place = ghost.label.placement;
  const v = await page.evaluate(([op, rid, start]) =>
    window.__cockpit.drag.dropAt(op, rid, start).then(() => window.__cockpit.drag.state().phase),
    [op, place.resource_id, place.start]);
  expect(v, "the drop reaches a verdict (not returned home)").toBe("verdict");
  const acc = await page.evaluate(() => window.__cockpit.drag.accept().then(() => ({
    state: window.__cockpit.drag.state(),
    placement: window.__cockpit.board.placementOf(window.__cockpit.drag.state().op),
  })));
  return { op, place, acc };
}

// 4.0 hotfix — R-DP1 on the RENDERED board. A GENUINE cross-machine drop (the
// ghost's target row ≠ the op's incumbent row) must, after accept + rebind,
// render the bar on the PINNED row — never snap back to the incumbent. The
// shipped backend silently skipped the machine pin when the target had no
// assignment literal, landing the op on the cheaper incumbent machine (right
// time, wrong machine); the Python end-to-end test pins the solver side, this
// pins the cockpit's gesture→send→rebind side. The 3.4/3.8 accept tests dropped
// onto ghosts too, but never asserted the target row DIFFERED from home.
test("a cross-machine drop renders the accepted bar on the PINNED row, not the incumbent (4.0 R-DP1)", async ({ page }) => {
  await boot(page);
  const ghost = priced.find((m) => {
    const inc = incumbent(m.label.target_operation_ref);
    return inc && m.label.placement.resource_id !== inc.resource_id;
  });
  expect(ghost, "the fixture carries a cross-machine ghost").toBeTruthy();
  const op = ghost.label.target_operation_ref;
  const home = incumbent(op).resource_id;
  const target = ghost.label.placement.resource_id;
  expect(target, "the drop genuinely crosses machines").not.toBe(home);

  const { acc } = await editAccept(page, ghost);
  expect(acc.state.phase).toBe("accepted");
  // the rendered bar sits on the PINNED row — not returned to its incumbent row.
  expect(acc.placement.group, "R-DP1: accepted bar rendered on the pinned machine").toBe(target);
  expect(acc.placement.group).not.toBe(home);
  await shot(page, "g13_cross_machine_rdp1");
});

test("two consecutive edit→accept cycles keep the cockpit bound to the live version (CU1, CU2)", async ({ page }) => {
  await boot(page);
  expect(priced.length, "the fixture carries ≥2 priced ghosts").toBeGreaterThanOrEqual(2);
  const base = (await boundIds(page)).hook;

  // cycle 1
  const c1 = await editAccept(page, priced[0]);
  expect(c1.acc.state.phase).toBe("accepted");
  const b1 = await boundIds(page);
  expect(b1.hook, "hook advanced off the base").not.toBe(base);
  expect(b1.controller, "controller agrees with the hook").toBe(b1.hook);
  expect(b1.url, "the address bar names the new version").toBe(b1.hook);
  // the accepted bar sits at the committed placement, not back home
  expect(c1.acc.placement.group).toBe(c1.place.resource_id);

  // cycle 2 — a SECOND edit on the already-rebound version (the seam that broke)
  const c2 = await editAccept(page, priced[1]);
  expect(c2.acc.state.phase, "the second accept succeeds against the live version").toBe("accepted");
  const b2 = await boundIds(page);
  expect(b2.hook, "the id advanced again").not.toBe(b1.hook);
  expect(b2.controller).toBe(b2.hook);
  expect(b2.url).toBe(b2.hook);
  // the SECOND accepted bar stays where committed
  expect(c2.acc.placement.group).toBe(c2.place.resource_id);
  expect(Math.abs(Date.parse(c2.acc.placement.start) - Date.parse(c2.place.start)))
    .toBeLessThanOrEqual(60000);
  await shot(page, "g12_two_cycles");
});

test("edit→accept→publish→edit: editing continues on the published version, never a superseded id (CU1, CU2)", async ({ page }) => {
  await boot(page);
  // edit → accept
  const c1 = await editAccept(page, priced[0]);
  expect(c1.acc.state.phase).toBe("accepted");
  const afterAccept = await boundIds(page);

  // publish → the published version is the schedule of record; the base is
  // superseded, but the cockpit is bound to the CHILD, not the superseded base.
  const pub = await page.evaluate(() => window.__cockpit.drag.publish().then(() => ({
    state: window.__cockpit.drag.state(),
    changed: window.__cockpit.versionChanged,
    url: new URLSearchParams(location.search).get("schedule"),
  })));
  expect(pub.state.phase).toBe("published");
  expect(pub.changed.status).toBe("published");
  expect(pub.url, "the URL still names the published version").toBe(afterAccept.hook);

  // edit AGAIN after publish — the drop must NOT 409 against a superseded id and
  // return home; it re-enters the accept path against the published version.
  const c2 = await editAccept(page, priced[1]);
  expect(c2.acc.state.phase, "post-publish edit reaches accept, not a superseded 409").toBe("accepted");
  const b2 = await boundIds(page);
  expect(b2.hook).not.toBe(afterAccept.hook);
  expect(b2.url).toBe(b2.hook);
  expect(c2.acc.placement.group).toBe(c2.place.resource_id);
  await shot(page, "g13_publish_then_edit");
});

test("a deep link to a superseded version loads read-only with a jump to current (CU3)", async ({ page }) => {
  // set up a superseded base: accept then publish supersedes it.
  await boot(page);
  await editAccept(page, priced[0]);
  await page.evaluate(() => window.__cockpit.drag.publish());
  // deep-link to the (now superseded) base id WITHOUT resetting lifecycle state.
  await page.goto(`/?schedule=${SCHEDULE}`);
  await page.waitForFunction(() => window.__cockpit && window.__cockpit.ready === true, { timeout: 20000 });
  expect(await page.evaluate(() => window.__cockpit.error || null)).toBeNull();
  // superseded → read-only banner + a one-click jump, and NO editable zombie.
  expect(await page.evaluate(() => window.__cockpit.superseded)).toBe(true);
  await expect(page.locator("#superseded-banner")).toBeVisible();
  await expect(page.locator("#sb-jump")).toBeVisible();
  expect(await page.evaluate(() => !!window.__cockpit.drag),
    "the gesture surface is not wired on a superseded version").toBe(false);
  await shot(page, "g14_superseded_deeplink");
});

test("discard from a verdict restores everything (CU5, R-DP7)", async ({ page }) => {
  await boot(page);
  const g = priced[0];
  const op = g.label.target_operation_ref;
  await page.evaluate(([op, rid, start]) =>
    window.__cockpit.drag.dropAt(op, rid, start),
    [op, g.label.placement.resource_id, g.label.placement.start]);
  await expect(page.locator(".delta-card")).toBeVisible();
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

// ---------------------------------------------------------------------------
// Session 3.4 — voice (CU3): the spoken-summary honesty contract + degrade
// ---------------------------------------------------------------------------

test("spoken summary leads with the register and NEVER voices record ids (CU3)", async ({ page }) => {
  await boot(page);
  const out = await page.evaluate(() => {
    const p = window.__cockpit.panel;
    const answer = "=== Why is WO-2001 late? ===\n"
      + "WO-2001 is 840 min late (record dec-1a2b3c4d, "
      + "op 3f2a9c11-2b3c-4d5e-6f70-8192a3b4c5d6 on M-GEAR-01).\nMore detail here.";
    return {
      testimony: p.spokenSummary(answer, "testimony"),
      judgment: p.spokenSummary(answer, "judgment"),
      voiceAvailable: p.voiceAvailable(),
    };
  });
  // register aloud, one sentence, planner vocabulary kept…
  expect(out.testimony.startsWith("Testimony.")).toBe(true);
  expect(out.judgment.startsWith("My take.")).toBe(true);
  expect(out.testimony).toContain("WO-2001");    // planner words are voiced
  // …but record ids are NEVER voiced (the screen holds the receipts)
  expect(out.testimony).not.toMatch(/dec-[0-9a-f]/i);
  expect(out.testimony).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}/i);
  // one sentence only (stops at the first period)
  expect(out.testimony).not.toContain("More detail");
});

test("the mic degrades without drama where speech is unsupported (CU3)", async ({ page }) => {
  await boot(page);
  // In a headless browser the mic either mounts (SpeechRecognition present) or
  // is silently removed — either way the typed composer is intact and nothing
  // throws. The honest contract is: no dead control, no crash.
  const state = await page.evaluate(() => ({
    micCount: document.querySelectorAll("#ask-mic").length,
    inputPresent: !!document.querySelector("#ask-input"),
    sendPresent: !!document.querySelector("#ask-send"),
    err: window.__cockpit.error || null,
  }));
  expect(state.err).toBe(null);
  expect(state.inputPresent && state.sendPresent).toBe(true);
  expect(state.micCount === 0 || state.micCount === 1).toBe(true);
});

// ---------------------------------------------------------------------------
// Session 3.7 — voice input hardening: tap-to-toggle model + layout stability.
// Headless has no microphone, so a FAKE SpeechRecognition (injected before the
// page scripts run) drives the REAL UI path — mic mount, toggle latch, interim
// overlay, submit — through the actual voice.js controller.
// ---------------------------------------------------------------------------

// The fake mimics the Web Speech shape the controller consumes (resultIndex +
// array-like results, each result[0].transcript + isFinal), in CONTINUOUS mode
// (the session lives until the user stops it). It registers itself on
// window.__lastRecognition so a test can push interim/final results and drive
// stop/abort. Enabled via window.__VOICE_TEST_RECOGNITION (honored by
// recognitionCtor() in voice.js — harness-only).
async function bootWithVoice(page) {
  await page.addInitScript(() => {
    class FakeRec {
      constructor() {
        window.__lastRecognition = this;
        this.lang = ""; this.interimResults = false; this.continuous = false;
        this.onresult = null; this.onend = null; this.onerror = null;
        this._results = []; this._running = false;
      }
      start() { this._running = true; this._results = []; }
      stop() { if (!this._running) return; this._running = false; this.onend && this.onend(); }
      abort() { if (!this._running) return; this._running = false; this.onend && this.onend(); }
      _emit(index) {
        if (!this.onresult) return;
        const results = this._results.map((r) => ({ isFinal: r.isFinal, 0: { transcript: r.transcript } }));
        this.onresult({ resultIndex: index, results });
      }
      __interim(text) {
        const last = this._results[this._results.length - 1];
        if (last && !last.isFinal) last.transcript = text;
        else this._results.push({ transcript: text, isFinal: false });
        this._emit(this._results.length - 1);
      }
      __final(text) {
        const last = this._results[this._results.length - 1];
        if (last && !last.isFinal) { last.transcript = text; last.isFinal = true; }
        else this._results.push({ transcript: text, isFinal: true });
        this._emit(this._results.length - 1);
      }
    }
    window.__VOICE_TEST_RECOGNITION = FakeRec;
  });
  await boot(page);
}

test("voice: tap latches recording; interim streaming NEVER moves the mic (CU1/CU2)", async ({ page }) => {
  await bootWithVoice(page);
  // the mic mounts (a recognizer is available via the injected fake)
  await expect(page.locator("#ask-mic")).toHaveCount(1);
  const box0 = await page.locator("#ask-mic").boundingBox();

  // tap → recording latches (unmistakable state: class + aria + overlay shown)
  const s1 = await page.evaluate(() => {
    window.__cockpit.panel.voice.toggle();
    const mic = document.querySelector("#ask-mic");
    return {
      state: window.__cockpit.panel.voiceState(),
      pressed: mic.getAttribute("aria-pressed"),
      recClass: mic.classList.contains("recording"),
      overlayShown: !document.querySelector("#ask-voice-overlay").classList.contains("hidden"),
    };
  });
  expect(s1.state).toBe("recording");
  expect(s1.pressed).toBe("true");
  expect(s1.recClass).toBe(true);
  expect(s1.overlayShown).toBe(true);

  // stream a LONG interim → the floating overlay fills; the mic box is unchanged
  await page.evaluate(() => window.__lastRecognition.__interim(
    "why is WO-2001 scheduled on machine M-GEAR-01 instead of the alternative route"));
  const overlayText = await page.locator("#ask-voice-text").textContent();
  expect(overlayText.length).toBeGreaterThan(30);
  const box1 = await page.locator("#ask-mic").boundingBox();
  for (const k of ["x", "y", "width", "height"]) {
    expect(Math.abs(box1[k] - box0[k]), `mic ${k} stable during interim`).toBeLessThanOrEqual(0.5);
  }
  // interim did not sever capture — still recording
  expect(await page.evaluate(() => window.__cockpit.panel.voice.listening())).toBe(true);

  // tap again → idle, overlay retired
  await page.evaluate(() => window.__cockpit.panel.voice.toggle());
  expect(await page.evaluate(() => window.__cockpit.panel.voiceState())).toBe("idle");
  expect(await page.locator("#ask-voice-overlay").evaluate((e) => e.classList.contains("hidden"))).toBe(true);
});

test("voice: the FULL transcript is submitted, never a leading fragment (regression)", async ({ page }) => {
  await bootWithVoice(page);
  const before = await page.locator(".ask .msg.you").count();
  await page.evaluate(() => window.__cockpit.panel.voice.toggle());   // start
  // words arrive incrementally — the OLD bug (button shifting under the held
  // pointer) severed capture and submitted only the first few.
  await page.evaluate(() => {
    const r = window.__lastRecognition;
    r.__interim("why");
    r.__interim("why is");
    r.__interim("why is WO-2001");
    r.__final("why is WO-2001 on M-GEAR-01");
  });
  // interim/final never stop the toggle session on their own
  expect(await page.evaluate(() => window.__cockpit.panel.voice.listening())).toBe(true);

  // stop → the WHOLE sentence lands + is submitted (the "you" message)
  await page.evaluate(() => window.__cockpit.panel.voice.toggle());   // stop
  const you = (await page.locator(".ask .msg.you pre").last().textContent()).trim();
  expect(you).toBe("why is WO-2001 on M-GEAR-01");   // not "why", not a fragment
  expect(await page.locator(".ask .msg.you").count()).toBe(before + 1);
});

test("voice: Escape cancels recording WITHOUT submitting (CU2)", async ({ page }) => {
  await bootWithVoice(page);
  const before = await page.locator(".ask .msg.you").count();
  await page.evaluate(() => window.__cockpit.panel.voice.toggle());   // start
  await page.evaluate(() => {
    const r = window.__lastRecognition;
    r.__interim("why is WO-2001");
    r.__final("why is WO-2001 on M-GEAR-01");
  });
  // Escape → cancel (discard the heard text)
  await page.keyboard.press("Escape");
  expect(await page.evaluate(() => window.__cockpit.panel.voiceState())).toBe("idle");
  // overlay retired, and NOTHING was submitted
  expect(await page.locator("#ask-voice-overlay").evaluate((e) => e.classList.contains("hidden"))).toBe(true);
  expect(await page.locator(".ask .msg.you").count()).toBe(before);
});

// ---------------------------------------------------------------------------
// Session 3.6 — R-M1: motion carries register (animation end-states)
// ---------------------------------------------------------------------------

test("R-M1a rejection: return-home is a snap-back (no settle) ending at origin", async ({ page }) => {
  await boot(page);
  const op = opFor("no_verdict");
  const inc = incumbent(op);
  const origin = await page.evaluate((o) => window.__cockpit.board.placementOf(o), op);
  // a canned no_verdict drop → REJECTION
  const obs = await page.evaluate(([o, rid, start]) =>
    window.__cockpit.drag.dropAt(o, rid, start).then(() => ({
      rejecting: !!document.querySelector(".carry-bar.rejecting"),   // the snap-back class
    })), [op, inc.resource_id, inc.start]);
  expect(obs.rejecting, "return-home uses the reject snap-back (R-M1a)").toBe(true);
  // after it completes the board is UNCHANGED — the op sits at its origin
  await page.waitForFunction(() => window.__cockpit.drag.state().phase === "idle", { timeout: 2000 });
  const after = await page.evaluate((o) => window.__cockpit.board.placementOf(o), op);
  expect(after).toEqual(origin);
  // the reason survives in the text channel (not the animation)
  await expect(page.locator(".delta-card.return-home")).toBeVisible();
});

test("R-M1b/c reflow is SIMULTANEOUS + the dropped bar pin-locks (own placement)", async ({ page }) => {
  await boot(page);
  const g = priced[0];
  const op = g.label.target_operation_ref;
  const rid = g.label.placement.resource_id, start = g.label.placement.start;
  await page.evaluate(([o, r, s]) => window.__cockpit.drag.dropAt(o, r, s), [op, rid, start]);
  const res = await page.evaluate(() => window.__cockpit.drag.accept().then(() => {
    const op = window.__cockpit.drag.state().op;
    const other = document.querySelector(".vis-item.bar:not(.pin-lock)");
    return {
      pinnedMotion: window.__cockpit.board.motionOf(op),
      pinnedPlacement: window.__cockpit.board.placementOf(op),
      // simultaneous — never staggered: no per-bar transition delay
      transitionDelay: other ? getComputedStyle(other).transitionDelay : "0s",
    };
  }));
  // R-M1c: OWN PLACEMENT — the dropped bar pin-locks, and it sits at the committed spot
  expect(res.pinnedMotion, "the dropped bar carries the pin-lock (R-M1c)").toContain("pin-lock");
  expect(res.pinnedPlacement.group, "the committed bar is on the dropped machine").toBe(rid);
  expect(Date.parse(res.pinnedPlacement.start)).toBe(Date.parse(start));
  // R-M1b: SIMULTANEOUS — no per-bar stagger/delay
  expect(res.transitionDelay).toBe("0s");
  await shot(page, "g12_pinlock_reflow");
});

test("R-M1d ghosts fade in WITH their labels (both layers, no independent pop)", async ({ page }) => {
  await boot(page);
  const op = priced[0].label.target_operation_ref;
  const st = await page.evaluate((o) => {
    window.__cockpit.drag.grab(o);
    return {
      ghosts: document.querySelectorAll(".drag-ghosts .ghost-bar").length,
      barsFade: !!document.querySelector(".drag-ghosts.ghost-fade"),
      labelsFade: !!document.querySelector(".drag-ghost-labels.ghost-fade"),
    };
  }, op);
  expect(st.ghosts).toBeGreaterThan(0);
  expect(st.barsFade && st.labelsFade, "bars AND labels fade together (R-M1d)").toBe(true);
});

test("R-M1 reduced-motion: instant transitions, semantics intact", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await boot(page);
  // rejection still returns to origin (no shake), still distinct via the card
  const op = opFor("no_verdict");
  const inc = incumbent(op);
  const origin = await page.evaluate((o) => window.__cockpit.board.placementOf(o), op);
  await page.evaluate(([o, r, s]) => window.__cockpit.drag.dropAt(o, r, s), [op, inc.resource_id, inc.start]);
  await page.waitForFunction(() => window.__cockpit.drag.state().phase === "idle", { timeout: 2000 });
  expect(await page.evaluate((o) => window.__cockpit.board.placementOf(o), op)).toEqual(origin);
  await expect(page.locator(".delta-card.return-home")).toBeVisible();   // meaning survives
  // accept still settles + pin-locks (end-state), but WITHOUT the reflow transition
  const g = priced[0];
  const gop = g.label.target_operation_ref;
  await page.evaluate(([o, r, s]) => window.__cockpit.drag.dropAt(o, r, s),
    [gop, g.label.placement.resource_id, g.label.placement.start]);
  const m = await page.evaluate(() => window.__cockpit.drag.accept().then(() => ({
    motion: window.__cockpit.board.motionOf(window.__cockpit.drag.state().op),
    reflowing: !!document.querySelector("#tl.reflowing"),
  })));
  expect(m.motion, "pin-lock confirmation present even under reduced motion").toContain("pin-lock");
  expect(m.reflowing, "no reflow transition class under reduced motion").toBe(false);
});
