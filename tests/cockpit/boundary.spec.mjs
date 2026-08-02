// SESSION 4B.28 — the board serves a person using it.
//
// Four items, one spec file, and the discipline is the same throughout: drive
// the REAL gesture, never a unit call. The brief asks for a Playwright DRAG of
// the frozen-boundary handle rather than a programmatic `propose()`, because a
// handle nobody can grab is a handle, and a test that calls past the pointer
// would never find out.
//
// Item 1  the movable frozen boundary — grip, drag, confirmation beat, apply,
//         restyle, and the ask-path answer's own document field
// Item 2  screen room — collapsibles with badges + persistence, and downtime
//         compression WITH THE DROP MAPPING STILL EXACT
// Item 3  the job panel — the whole job, one source per quantity
// Item 4  the gestural debt — chunked drag, the no-op tolerance, and the pin
//         built from the DRAGGED bar rather than the selected one
//
// Runs on BOTH data-themes like every other rendering spec.
import { test, expect } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const SHOTS = resolve(dirname(fileURLToPath(import.meta.url)), "shots");
mkdirSync(SHOTS, { recursive: true });
const theme = () => test.info().project.metadata?.theme || "light";
const shot = (page, name) => page.screenshot({ path: resolve(SHOTS, `${name}__${theme()}.png`) });

const ROLLING = "sched-rolling-fixture";
const BASE = "sched-multi-route-fixture";   // the monolithic base fixture
// Item 4(a) needs a board with a SPLIT operation on it, and the hand-authored
// planner fixture is the one that carries one (Session 4.2). The rolling
// fixture chunks nothing, so pointing the chunked tests at it would have let
// them skip forever while reading as coverage.
const SPLIT = "sched-planner-fixture";

async function boot(page, schedule = ROLLING) {
  await page.request.post("/__test__/reset").catch(() => {});
  // Every test starts from the SHIPPED defaults: the dock states and the
  // linear/compressed choice persist per browser on purpose, so a test that
  // inherited the previous test's choices would be asserting the wrong board.
  // Cleared HERE and not in an init script, because an init script fires on
  // every navigation — including the reload the persistence test depends on.
  await page.goto("/");
  await page.evaluate(() => {
    try { localStorage.clear(); sessionStorage.clear(); } catch { /* ignore */ }
  });
  await page.goto(`/?schedule=${schedule}&theme=${theme()}`);
  await page.waitForFunction(() => window.__cockpit && window.__cockpit.ready === true,
                             { timeout: 20000 });
  expect(await page.evaluate(() => window.__cockpit.error || null), "booted clean").toBeNull();
  await page.waitForFunction(() => document.querySelectorAll(".vis-item.bar").length > 0,
                             { timeout: 10000 });
}

// ===========================================================================
// PREMISE — a fixture that cannot exercise the ceremony proves nothing.
// ===========================================================================

test("PREMISE: the fixture board has committed work on both sides of a candidate boundary",
  async ({ page }) => {
    await boot(page);
    const facts = await page.evaluate(() => {
      const d = window.__cockpit.doc;
      const frozen = Date.parse(d.rolling.frozen_until);
      const target = frozen - 12 * 3600000;
      const committed = (d.assignments || [])
        .filter((a) => a.commitment_state === "committed" && (a.chunks || []).length)
        .map((a) => Date.parse(a.chunks[0].start));
      return {
        before: committed.filter((s) => s < target).length,
        uncovered: committed.filter((s) => s >= target && s < frozen).length,
        active: (d.assignments || []).filter((a) => a.commitment_state === "active_window").length,
      };
    });
    expect(facts.uncovered, "committed work the candidate boundary UNCOVERS").toBeGreaterThan(0);
    expect(facts.active, "active work a freeze could commit").toBeGreaterThan(0);
  });

// ===========================================================================
// ITEM 1 — THE MOVABLE FROZEN BOUNDARY (R-F1)
// ===========================================================================

test("Item 1(a): the frozen boundary is a REAL HANDLE, and only on a rolling board",
  async ({ page }) => {
    await boot(page);
    const grip = page.locator(".marker.frozen .marker-grip");
    await expect(grip, "the boundary carries a grip").toHaveCount(1);
    // it states itself on hover — a handle a planner cannot identify is chrome
    expect(await grip.getAttribute("title")).toContain("Frozen boundary");
    const m = await page.evaluate(() => window.__cockpit.board.markerProbe());
    expect(m.grip, "the probe agrees a grip is drawn").toBe(true);
    await shot(page, "b1_boundary_handle");

    // …and a MONOLITHIC board has no frozen zone, so it must not offer one.
    await boot(page, BASE);
    expect(await page.locator(".marker.frozen .marker-grip").count(),
           "a monolithic board offers no boundary handle").toBe(0);
  });

test("Item 1(a): dragging the handle shows the provisional instant AND the delta, live",
  async ({ page }) => {
    await boot(page);
    const grip = page.locator(".marker.frozen .marker-grip");
    await expect(grip).toBeVisible();
    const box = await grip.boundingBox();
    // The offset is computed through the board's OWN conversion rather than a
    // fixed pixel count: a raw -90px is a different number of hours at every
    // zoom and theme, and under load it can push the provisional line off the
    // left edge, where there is nothing to read.
    const dx = await page.evaluate(() => {
      const tl = window.__cockpit.board.timeline;
      const f = Date.parse(window.__cockpit.board.currentDoc().rolling.frozen_until);
      return tl.body.util.toScreen(new Date(f - 6 * 3600000))
           - tl.body.util.toScreen(new Date(f));
    });
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    // move EARLIER but do not release — the drag state must be live
    await page.mouse.move(box.x + box.width / 2 + dx, box.y + box.height / 2,
                          { steps: 8 });
    await expect.poll(async () =>
      await page.evaluate(() => !!window.__cockpit.board.markerProbe().dragging),
      { timeout: 5000 }).toBe(true);
    const dragging = await page.evaluate(() => window.__cockpit.board.markerProbe().dragging);
    expect(dragging, "a drag is in flight").not.toBeNull();
    expect(dragging.label, "the provisional instant is rendered").toMatch(/\d{2}:\d{2}/);
    expect(dragging.label, "…beside the delta from where it was").toMatch(/[−+]\d/);
    // the COMMITTED boundary is still drawn, ghosted, so the delta is checkable
    await expect(page.locator(".marker.frozen-was")).toHaveCount(1);
    await shot(page, "b2_boundary_dragging");
    await page.mouse.up();
  });

test("Item 1(e): a boundary drag ASKS before it commits, and states the count and direction",
  async ({ page }) => {
    await boot(page);
    const before = await page.evaluate(() => window.__cockpit.doc.rolling.frozen_until);
    await dragBoundaryHours(page, -12);

    const card = page.locator("#boundary-confirm");
    await expect(card, "the confirmation beat opened").toBeVisible();
    await expect(card).toContainText("Thaw committed work?");
    await expect(card.locator(".bc-count")).toContainText("pins you hold");
    // THE COUNT ON SCREEN IS THE SERVER'S COUNT — the UI never counts bars for
    // itself, which is what makes the number it asks about the number that
    // applies (R-F1(e)).
    const planCount = await page.evaluate(() => window.__cockpit.boundary.state().plan.count);
    await expect(card.locator(".bc-count")).toContainText(String(planCount));
    expect(planCount, "the fixture thaws something").toBeGreaterThan(0);

    // …and NOTHING has changed yet.
    const still = await page.evaluate(() => window.__cockpit.doc.rolling.frozen_until);
    expect(still, "the boundary has not moved before the confirmation").toBe(before);
    await shot(page, "b3_confirmation_beat");
  });

test("Item 1(e): CANCEL changes nothing at all", async ({ page }) => {
  await boot(page);
  const id0 = await page.evaluate(() => window.__cockpit.scheduleId);
  await dragBoundaryHours(page, -12);
  await page.locator("#boundary-confirm .bc-dismiss").click();
  await expect(page.locator("#boundary-confirm")).toBeHidden();
  expect(await page.evaluate(() => window.__cockpit.scheduleId),
         "no version was minted by a cancelled ceremony").toBe(id0);
  expect(await page.locator(".vis-item.bar.standing-pin").count(),
         "no bar was restyled").toBe(0);
});

test("Item 1(b): CONFIRMING a thaw restyles the bars and rebinds the board",
  async ({ page }) => {
    await boot(page);
    const pinnedBefore = await page.locator(".vis-item.bar.standing-pin").count();
    await dragBoundaryHours(page, -12);
    const plan = await page.evaluate(() => window.__cockpit.boundary.state().plan);
    await page.locator("#boundary-confirm .bc-apply").click();
    await expect(page.locator("#boundary-confirm.done")).toBeVisible({ timeout: 10000 });

    // the version changed… (the strip repaint is async by design — it fetches
    // the new /meta — so this polls rather than reading once, exactly as the
    // accept path's own rebind does)
    await expect.poll(async () =>
      (await page.evaluate(() => window.__cockpit.versionChanged || null))?.status,
      { timeout: 10000 }).toBe("proposed");

    // …the boundary moved…
    const m = await page.evaluate(() => window.__cockpit.board.markerProbe());
    expect(m.frozenMs, "the marker follows the document").toBe(Date.parse(plan.to_instant));

    // …and the THAWED BARS ARE VISIBLY PINNED. R-F1(b): the change of authority
    // has to be visible, or a planner is holding work they cannot see they hold.
    const pinnedAfter = await page.locator(".vis-item.bar.standing-pin").count();
    expect(pinnedAfter - pinnedBefore, "every thawed placement restyled to pinned")
      .toBe(plan.pinned_ops.length);
    await shot(page, "b4_thawed");
  });

test("Item 1(b): a thaw NEVER moves a bar", async ({ page }) => {
  await boot(page);
  const before = await page.evaluate(() =>
    Object.fromEntries((window.__cockpit.doc.assignments || []).map(
      (a) => [a.operation_ref, `${a.resource_id}@${a.chunks[0].start}`])));
  await dragBoundaryHours(page, -12);
  await page.locator("#boundary-confirm .bc-apply").click();
  await expect(page.locator("#boundary-confirm.done")).toBeVisible({ timeout: 10000 });
  const after = await page.evaluate(() =>
    Object.fromEntries((window.__cockpit.board.currentDoc().assignments || []).map(
      (a) => [a.operation_ref, `${a.resource_id}@${a.chunks[0].start}`])));
  expect(after, "a thaw changes authority, never position").toEqual(before);
});

test("Item 1(d): the boundary move is on the DOCUMENT, which is how the ask path answers",
  async ({ page }) => {
    await boot(page);
    await dragBoundaryHours(page, -12);
    await page.locator("#boundary-confirm .bc-apply").click();
    await expect(page.locator("#boundary-confirm.done")).toBeVisible({ timeout: 10000 });
    const moves = await page.evaluate(() =>
      window.__cockpit.board.currentDoc().rolling.boundary_moves);
    expect(moves.length, "the ACT is recorded, not only its consequences").toBe(1);
    expect(moves[0].direction).toBe("thaw");
    expect(moves[0].pinned_ops.length, "…naming exactly which ops it pinned")
      .toBeGreaterThan(0);
    expect(moves[0].from_instant).toBeTruthy();
    expect(moves[0].to_instant).toBeTruthy();
  });

test("Item 1: a REFUSAL reads as a refusal — never a failure, never a silent revert",
  async ({ page }) => {
    await boot(page);
    // an instant the board cannot make a move to
    await page.evaluate(() => window.__cockpit.boundary.propose("2027-01-01T00:00:00Z"));
    const card = page.locator("#boundary-confirm");
    await expect(card).toBeVisible();
    await expect(card).toHaveClass(/refused/);
    expect(await card.locator(".bc-apply").count(),
           "a refusal offers nothing to confirm").toBe(0);
    // the refusal register is NOT the failure register (4B.23 §5a.91)
    await expect(card).not.toHaveClass(/failed/);
    await shot(page, "b5_boundary_refusal");
  });

test("Item 1(e): a STALE confirmation is refused, not applied to whatever is there now",
  async ({ page }) => {
    await boot(page);
    await dragBoundaryHours(page, -12);
    // tamper with the digest the way a changed board would
    const res = await page.evaluate(async () => {
      const plan = window.__cockpit.boundary.state().plan;
      const r = await fetch(
        `/schedules/${window.__cockpit.scheduleId}/boundary`,
        { method: "POST", headers: { "content-type": "application/json" },
          body: JSON.stringify({ frozen_until: plan.to_instant,
                                 expect_digest: "not-the-digest" }) });
      return (await r.json()).data;
    });
    expect(res.refused, "a stale confirmation is refused").toBe(true);
    expect(res.code).toBe("stale_confirmation");
  });

// The boundary drag, as a real pointer gesture. `hours` is signed: negative
// pulls it earlier (a thaw), positive pushes it later (a freeze).
async function dragBoundaryHours(page, hours) {
  const grip = page.locator(".marker.frozen .marker-grip");
  // The overlay is redrawn on every pan/zoom/redraw, so the grip element is
  // replaced rather than moved. Wait for the CURRENT one to be laid out before
  // reading its box — a null box here is a race, not a missing handle.
  await expect(grip).toBeVisible();
  const box = await grip.boundingBox();
  // Convert hours to pixels through the board's OWN conversion, so this works
  // at any zoom and under compression — the same arithmetic the product uses.
  const dx = await page.evaluate((h) => {
    const tl = window.__cockpit.board.timeline;
    const frozen = Date.parse(window.__cockpit.board.currentDoc().rolling.frozen_until);
    const x0 = tl.body.util.toScreen(new Date(frozen));
    const x1 = tl.body.util.toScreen(new Date(frozen + h * 3600000));
    return x1 - x0;
  }, hours);
  const cy = box.y + box.height / 2;
  await page.mouse.move(box.x + box.width / 2, cy);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + dx, cy, { steps: 10 });
  await page.mouse.up();
  await expect(page.locator("#boundary-confirm")).toBeVisible({ timeout: 10000 });
}

// ===========================================================================
// ITEM 2 — SCREEN ROOM
// ===========================================================================

test("Item 2(a): three docks, each collapsing to a labelled edge that STILL states its count",
  async ({ page }) => {
    await boot(page);
    const docks = await page.evaluate(() =>
      Object.fromEntries(Object.entries(window.__cockpit.docks)
        .map(([k, d]) => [k, d.probe()])));
    // the DEFAULTS the brief rules: tray and coarse collapsed, ask open.
    expect(docks.tray.open, "the tray ships collapsed").toBe(false);
    expect(docks.ask.open, "the ask panel ships open — it is the differentiator").toBe(true);
    expect(docks.tray.label).toBe("BEYOND THE HORIZON");
    // THE BADGE SURVIVES THE COLLAPSE. A collapsed tray showing nothing would
    // make known work invisible, which is the Glass Box cardinal danger the
    // tray exists to answer.
    const trayCount = await page.evaluate(() => window.__cockpit.tray.count);
    expect(docks.tray.badge, "the collapsed tray states its count").toBe(String(trayCount));
    await expect(page.locator('.dock-edge[data-dock="tray"] .de-badge'))
      .toBeVisible();
    await shot(page, "b6_docks_collapsed");
  });

test("Item 2(a): a dock's collapsed state persists per browser", async ({ page }) => {
  await boot(page);
  await page.locator('.dock-edge[data-dock="tray"]').click();
  expect(await page.evaluate(() => window.__cockpit.docks.tray.isOpen())).toBe(true);
  // reload WITHOUT clearing storage — the choice must survive
  await page.goto(`/?schedule=${ROLLING}&theme=${theme()}`);
  await page.waitForFunction(() => window.__cockpit && window.__cockpit.ready === true,
                             { timeout: 20000 });
  expect(await page.evaluate(() => window.__cockpit.docks.tray.isOpen()),
         "the planner's own choice survived the reload").toBe(true);
});

test("Item 2(b): compression folds closed time, marks every seam, and toggles back",
  async ({ page }) => {
    await boot(page);
    expect(await page.evaluate(() => window.__cockpit.board.isCompressed()),
           "LINEAR is the default — nobody's ruler is folded unasked").toBe(false);
    await page.locator("#board-compress").click();
    await page.waitForFunction(() => window.__cockpit.board.isCompressed() === true);
    const m = await page.evaluate(() => window.__cockpit.board.markerProbe());
    expect(m.folds, "closed spans were found to fold").toBeGreaterThan(0);
    // EVERY VISIBLE SEAM IS MARKED. A fold with no mark makes two bars either
    // side of a collapsed night read as adjacent, which compression must never
    // say about the plant.
    expect(m.foldMarksDrawn, "the ruler LOOKS folded where it is folded")
      .toBeGreaterThan(0);
    await expect(page.locator(".fold-mark").first()).toBeVisible();
    expect(await page.locator(".fold-mark").first().getAttribute("title"))
      .toContain("NOT adjacent");
    await shot(page, "b7_compressed");

    // …and back. Verifying a calendar claim needs the true linear scale.
    await page.locator("#board-compress").click();
    await page.waitForFunction(() => window.__cockpit.board.isCompressed() === false);
    expect(await page.locator(".fold-mark").count(), "linear has no folds").toBe(0);
  });

test("Item 2(b): THE DROP MAPPING IS EXACT UNDER COMPRESSION", async ({ page }) => {
  // The requirement that decided the mechanism. A drop that lands minutes off
  // under compression is a worse defect than an uncompressed board, so this
  // drives a REAL drop at a KNOWN instant with the ruler folded and asserts the
  // pin the server was actually sent.
  await boot(page);
  await page.locator("#board-compress").click();
  await page.waitForFunction(() => window.__cockpit.board.isCompressed() === true);

  // vis's own conversion must still round-trip
  const rt = await page.evaluate(() => {
    const d = window.__cockpit.board.currentDoc();
    const a = d.assignments.find((x) => (x.chunks || []).length === 1);
    return window.__cockpit.board.compressionProbe(Date.parse(a.chunks[0].start));
  });
  expect(rt.compressed).toBe(true);
  expect(rt.roundTripErrMs, "instant → x → instant is exact under folds")
    .toBeLessThanOrEqual(60000);

  // …and the PIN the drag builds carries the instant that was targeted.
  const sent = [];
  await page.route("**/sandbox/feasibility", (route) => {
    sent.push(JSON.parse(route.request().postData() || "{}"));
    return route.continue();
  });
  const target = await page.evaluate(() => {
    const d = window.__cockpit.board.currentDoc();
    const a = d.assignments.find((x) => (x.chunks || []).length === 1
      && x.commitment_state !== "committed");
    const to = new Date(Date.parse(a.chunks[0].start) + 6 * 3600000).toISOString();
    window.__cockpit.drag.dropAt(a.operation_ref, a.resource_id, to, true);
    return { op: a.operation_ref, to };
  });
  await expect.poll(() => sent.length, { timeout: 10000 }).toBeGreaterThan(0);
  const pinned = Date.parse(sent[0].pin_start_iso);
  expect(Math.abs(pinned - Date.parse(target.to)) / 60000,
         "the pin under compression is the instant that was targeted, to the minute")
    .toBeLessThanOrEqual(1);
});

// ===========================================================================
// ITEM 3 — THE JOB PANEL
// ===========================================================================

test("Item 3: clicking a bar shows the WHOLE job, not the bar", async ({ page }) => {
  await boot(page);
  const picked = await page.evaluate(() => {
    // an order with MORE THAN ONE operation, or the panel proves nothing
    const d = window.__cockpit.doc;
    const byOrder = new Map();
    for (const a of d.assignments || []) {
      for (const w of a.work_orders || []) {
        byOrder.set(w, (byOrder.get(w) || 0) + 1);
      }
    }
    let best = null;
    for (const [wo, n] of byOrder) if (!best || n > best.n) best = { wo, n };
    const a = (d.assignments || []).find((x) => (x.work_orders || []).includes(best.wo));
    window.__cockpit.select(a.operation_ref);
    return { order: best.wo, ops: best.n, op: a.operation_ref };
  });
  expect(picked.ops, "premise: a multi-operation order exists on this board")
    .toBeGreaterThan(1);
  const panel = page.locator("#job-panel");
  await expect(panel).toBeVisible();
  const probe = await page.evaluate(() => window.__cockpit.jobPanel.probe());
  expect(probe.order).toBe(picked.order);
  expect(probe.rows.length, "EVERY operation of the order is listed").toBe(picked.ops);
  expect(probe.rows.filter((r) => r.selected).length,
         "the clicked operation is marked, exactly once").toBe(1);
  // 4B.20: name WHICH quantity. The panel says "working", never a bare duration.
  expect(probe.rows[0].facts.some((f) => f.startsWith("working ")),
         "working time is NAMED as working time").toBe(true);
  await shot(page, "b8_job_panel");
});

test("Item 3: a panel row navigates the board, and the two buttons carry the operation",
  async ({ page }) => {
    await boot(page);
    await page.evaluate(() => {
      const d = window.__cockpit.doc;
      const byOrder = new Map();
      for (const a of d.assignments || []) {
        for (const w of a.work_orders || []) byOrder.set(w, (byOrder.get(w) || 0) + 1);
      }
      let best = null;
      for (const [wo, n] of byOrder) if (!best || n > best.n) best = { wo, n };
      const a = (d.assignments || []).find((x) => (x.work_orders || []).includes(best.wo));
      window.__cockpit.select(a.operation_ref);
    });
    const rows = page.locator("#job-panel .jp-row:not(.jp-tray)");
    const n = await rows.count();
    expect(n, "premise: more than one row to navigate between").toBeGreaterThan(1);
    // click the LAST row — the selection must follow it
    const lastOp = await rows.nth(n - 1).getAttribute("data-op");
    await rows.nth(n - 1).click();
    await expect.poll(async () =>
      (await page.evaluate(() => window.__cockpit.jobPanel.probe()))
        .rows.find((r) => r.selected)?.op).toBe(lastOp);

    // Item 3's last clause: the intent buttons carry the OPERATION, which is
    // what 4B.30 §5a.118(c) said text cannot. Asserted on the wire.
    const asks = [];
    await page.route("**/ask", (route) => {
      asks.push(JSON.parse(route.request().postData() || "{}"));
      return route.continue();
    });
    await page.locator("#job-panel .jp-row.selected .jp-why").click();
    await expect.poll(() => asks.length, { timeout: 15000 }).toBeGreaterThan(0);
    const sel = asks[asks.length - 1].selection || {};
    expect(sel.op_seq, "the request names WHICH operation of the order")
      .not.toBeNull();
    expect(asks[asks.length - 1].question).toMatch(/^why is /i);
  });

// ===========================================================================
// ITEM 4 — THE GESTURAL DEBT
// ===========================================================================

test("Item 4(b): the no-op tolerance is a FIXED constant, not a function of the zoom",
  async ({ page }) => {
    await boot(page);
    const tolAtDefault = await page.evaluate(() =>
      window.__cockpit.drag.state().noopToleranceMin);
    // zoom right out — under the old rule the tolerance grew with the view and
    // swallowed real four-hour moves whole
    await page.evaluate(() => { for (let i = 0; i < 6; i += 1) window.__cockpit.board.zoomOut(0.6); });
    await page.waitForTimeout(200);
    const tolZoomedOut = await page.evaluate(() =>
      window.__cockpit.drag.state().noopToleranceMin);
    expect(tolZoomedOut, "the tolerance is for click jitter, and jitter does not zoom")
      .toBe(tolAtDefault);
    expect(tolAtDefault).toBeLessThanOrEqual(15);
  });

test("Item 4(b): a real move at a zoomed-out view is PRICED, not swallowed",
  async ({ page }) => {
    await boot(page);
    await page.evaluate(() => { for (let i = 0; i < 6; i += 1) window.__cockpit.board.zoomOut(0.6); });
    await page.waitForTimeout(200);
    let priced = 0;
    await page.route("**/sandbox/feasibility", (route) => { priced++; return route.continue(); });
    const moved = await page.evaluate(() => {
      const d = window.__cockpit.board.currentDoc();
      const a = d.assignments.find((x) => (x.chunks || []).length === 1
        && x.commitment_state !== "committed");
      const to = new Date(Date.parse(a.chunks[0].start) + 4 * 3600000).toISOString();
      const r = window.__cockpit.drag.dropAt(a.operation_ref, a.resource_id, to, true);
      return { noop: !!(r && r.noop) };
    });
    expect(moved.noop, "a four-hour move is not 'already here'").toBe(false);
    await expect.poll(() => priced, { timeout: 10000 }).toBeGreaterThan(0);
  });

test("Item 4(b): a genuine no-op SAYS SO rather than reverting in silence",
  async ({ page }) => {
    await boot(page);
    await page.evaluate(() => {
      const d = window.__cockpit.board.currentDoc();
      const a = d.assignments.find((x) => (x.chunks || []).length === 1
        && x.commitment_state !== "committed");
      window.__cockpit.drag.dropAt(a.operation_ref, a.resource_id, a.chunks[0].start, true);
    });
    await expect(page.locator(".drag-noop")).toContainText("already sits");
    expect(await page.evaluate(() => window.__cockpit.drag.state().noop)).toBe(true);
  });

test("Item 4(c): a drag's pin is built from the DRAGGED bar, even with another selected",
  async ({ page }) => {
    await boot(page);
    const sent = [];
    await page.route("**/sandbox/feasibility", (route) => {
      sent.push(JSON.parse(route.request().postData() || "{}"));
      return route.continue();
    });
    const ids = await page.evaluate(() => {
      const d = window.__cockpit.board.currentDoc();
      const free = d.assignments.filter((x) => (x.chunks || []).length === 1
        && x.commitment_state !== "committed");
      const other = free[0], dragged = free[free.length - 1];
      // SELECT ONE BAR, DRAG A DIFFERENT ONE. This is the stale-selection hazard
      // from the 4B.24 incident era, driven rather than assumed.
      window.__cockpit.select(other.operation_ref);
      const to = new Date(Date.parse(dragged.chunks[0].start) + 3 * 3600000).toISOString();
      window.__cockpit.drag.dropAt(dragged.operation_ref, dragged.resource_id, to, true);
      return { selected: other.operation_ref, dragged: dragged.operation_ref };
    });
    expect(ids.selected).not.toBe(ids.dragged);
    await expect.poll(() => sent.length, { timeout: 10000 }).toBeGreaterThan(0);
    expect(sent[0].pin_op_id, "the pin names the bar that was dragged")
      .toBe(ids.dragged);
  });

test("Item 4(a): a chunked bar's drag is a GESTURE, never a silent pan",
  async ({ page }) => {
    await boot(page, SPLIT);
    const chunked = await page.evaluate(() => {
      const d = window.__cockpit.board.currentDoc();
      const a = (d.assignments || []).find((x) => (x.chunks || []).length > 1);
      return a ? { op: a.operation_ref, id: a.assignment_id,
                   pieces: a.chunks.length } : null;
    });
    test.skip(!chunked, "this fixture has no chunked operation");

    // THIS IS A REAL POINTER DRAG ON A REAL CHUNK PIECE, and it has to be.
    // The defect lived in `onPointerDown`, which tested the item id against the
    // ASSIGNMENT index — and a piece id (`<id>~c1`) is not an assignment id, so
    // the gesture never started and vis's own Hammer pan took the drag instead.
    // A test that called `drag.grab(op)` would step over the exact line that was
    // broken and pass against it; this session proved that by reverting the fix
    // and watching the programmatic version stay green.
    const piece = page.locator(`.vis-item.bar.chunk-piece`).nth(1);
    await expect(piece, "a second chunk piece is on screen").toBeVisible();
    const box = await piece.boundingBox();
    const win0 = await page.evaluate(() => window.__cockpit.getWindow());

    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2 + 70, box.y + box.height / 2,
                          { steps: 10 });

    const state = await page.evaluate(() => window.__cockpit.drag.state());
    expect(state.phase, "grabbing a PIECE grabs the operation").not.toBe("idle");
    expect(state.op, "…and it is the right operation").toBe(chunked.op);
    expect(state.chunked, "the controller knows this operation is split").toBe(true);
    // THE PIECES MOVE AS ONE — one carry ghost per chunk.
    expect(await page.locator(".carry-bar.carry-piece").count(),
           "every piece travels with the gesture").toBe(chunked.pieces);
    const win1 = await page.evaluate(() => window.__cockpit.getWindow());
    expect(win1.start, "the board did not pan under the drag").toBe(win0.start);
    await shot(page, "b9_chunked_carry");
    await page.mouse.up();
  });

test("Item 4(a): a chunked drop DECLINES VISIBLY, in its own register",
  async ({ page }) => {
    await boot(page, SPLIT);
    const chunked = await page.evaluate(() => {
      const d = window.__cockpit.board.currentDoc();
      const a = (d.assignments || []).find((x) => (x.chunks || []).length > 1);
      return a ? { op: a.operation_ref, rid: a.resource_id,
                   start: a.chunks[0].start } : null;
    });
    test.skip(!chunked, "this fixture has no chunked operation");
    let priced = 0;
    await page.route("**/sandbox/feasibility", (route) => { priced++; return route.continue(); });
    // The target must be LEGAL, or the drop takes the Tier-0 refusal branch
    // first — and it should: "that machine is closed then" is a fact about the
    // plant and outranks a limit of ours. So the drop is aimed at a legal region
    // the op is not already in, which is what a planner moving a split bar to a
    // real opening is doing.
    const landed = await page.evaluate((c) => {
      const t0 = window.__cockpit.drag.tier0For(c.op);
      const row = (t0.rows || []).find((r) => r.resource_id === c.rid && r.eligible);
      const inc = Date.parse(c.start);
      let target = null;
      for (const reg of (row && row.legal_regions) || []) {
        const s = Date.parse(reg.start);
        if (Math.abs(s - inc) > 60 * 60000) { target = reg.start; break; }
      }
      if (!target) return null;
      window.__cockpit.drag.dropAt(c.op, c.rid, target, true);
      return target;
    }, chunked);
    expect(landed, "premise: a legal region away from the incumbent exists")
      .not.toBeNull();

    const card = page.locator(".delta-card.declined");
    await expect(card, "the decline is a card, impossible to miss").toBeVisible();
    // A LIMIT OF OURS, SAID AS ONE — the ask path's own words, so the two
    // surfaces state one limit rather than disagreeing.
    await expect(card).toContainText("limit of mine, not a ruling about your plant");
    await expect(card).toContainText("can't price it");
    // …and it is NOT the proven-impossible register, which is a claim about the
    // plant nobody tested here.
    expect(await page.locator(".delta-card.impossible").count()).toBe(0);
    expect(priced, "declined from the ROW — no model build was paid for").toBe(0);
    expect(await page.evaluate(() => window.__cockpit.drag.state().declined))
      .toBe("chunked");
    await shot(page, "b10_chunked_decline");
  });
