// Session 4B.3c — the R-T2 two-beat + the ask-why bridge, on a REAL SLICED
// (rolling-horizon) board. The rolling fixture now carries a Tier-0 interaction
// payload for its ACTIVE WINDOW (CU2), so the gesture surface stands up on a
// rolling board exactly as on a monolithic one; the canned feasibility/sandbox
// responses were captured from the REAL backend two-beat against the persisted
// window-0 run (CU1), so this exercises the true flow hermetically.
//
// Committed (frozen-front) bars carry NO interaction op, so they are non-targets
// by construction — the only gesturable ops are active-window ops.
import { test, expect } from "@playwright/test";
import { mkdirSync, readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SHOTS = resolve(HERE, "shots");
mkdirSync(SHOTS, { recursive: true });
const theme = () => test.info().project.metadata?.theme || "light";
const shot = (page, name) => page.screenshot({ path: resolve(SHOTS, `${name}__${theme()}.png`) });

const SCHEDULE = "sched-rolling-fixture";
const DIR = resolve(HERE, "fixtures", "rolling");
const load = (n) => JSON.parse(readFileSync(resolve(DIR, n), "utf-8"));
const gesture = load("gesture.json");

async function boot(page) {
  await page.request.post("/__test__/reset").catch(() => {});
  await page.goto(`/?schedule=${SCHEDULE}&theme=${theme()}`);
  await page.waitForFunction(() => window.__cockpit && window.__cockpit.ready === true, { timeout: 20000 });
  expect(await page.evaluate(() => window.__cockpit.error || null)).toBeNull();
  await page.waitForFunction(() => document.querySelectorAll(".vis-item.bar").length > 0, { timeout: 10000 });
  // the gesture surface stands up once the interaction payload + (absent)
  // alternatives resolve — alternativesReady flips true even on a 404.
  await page.waitForFunction(() => window.__cockpit.drag && window.__cockpit.alternativesReady === true, { timeout: 10000 });
  expect(await page.evaluate(() => window.__cockpit.dragError || null)).toBeNull();
}

// A Tier-0-legal start on a SPECIFIC target resource for op (a cross-machine
// move) — mirrors gesture.spec's legalMove but filters rows to the target row.
async function legalMoveTo(page, op, rid) {
  const mv = await page.evaluate(([op, rid]) => {
    const d = window.__cockpit.drag;
    const row = (d.tier0For(op).rows || []).find((r) => r.resource_id === rid);
    if (!row) return null;
    for (const reg of row.legal_regions || []) {
      const s = Date.parse(reg.start), e = Date.parse(reg.end);
      for (const cand of [s, Math.floor((s + e) / 2), e]) {
        if (cand >= s && cand <= e) return { resource_id: rid, start: new Date(cand).toISOString() };
      }
    }
    return null;
  }, [op, rid]);
  return mv;   // may be null if the target row has no legal region in-window
}

test("R-T2 rolling: the gesture surface stands up on a sliced board (active ops only)", async ({ page }) => {
  await boot(page);
  const info = await page.evaluate((op) => {
    const d = window.__cockpit.drag;
    // committed bars carry no interaction op → tier0For returns no eligible rows.
    const t = d.tier0For(op);
    return { rows: (t.rows || []).length, rolling: !!window.__cockpit.doc.rolling };
  }, gesture.op);
  expect(info.rolling).toBe(true);
  expect(info.rows).toBeGreaterThan(0);   // the active gesture op is draggable
  await shot(page, "rolling_2beat_ready");
});

test("R-T2 rolling: drag an active op cross-machine → feasibility ghost → priced layered card", async ({ page }) => {
  await boot(page);
  const mv = (await legalMoveTo(page, gesture.op, gesture.resource))
    || { resource_id: gesture.resource, start: gesture.start };
  const st = await page.evaluate(([op, rid, start]) =>
    window.__cockpit.drag.dropAt(op, rid, start, /*altKey*/ true)
      .then(() => window.__cockpit.drag.state()),
    [gesture.op, mv.resource_id, mv.start]);
  // beat one produced a feasibility ghost; beat two a correlated verdict
  expect(st.phase).toBe("verdict");
  expect(st.correlationId).toBeTruthy();
  expect(st.feasibilityGhost && st.feasibilityGhost.feasible).toBe(true);
  const card = page.locator(".delta-card.verdict");
  await expect(card).toBeVisible();
  // the always-visible layer: placement + the committed-safe note (load-bearing
  // on a rolling board — the frozen front must be untouched)
  await expect(page.locator(".delta-card .dc-note.committed-safe")).toBeVisible();
  // the detail layer discloses the cost-by-line decomposition
  const detail = page.locator(".delta-card .dc-detail-layer");
  await expect(detail).toHaveCount(1);
  await shot(page, "rolling_2beat_card");
});

test("CU1: the priced card SPLITS its verdict — window re-optimization vs your move", async ({ page }) => {
  // The founder's trust item, rendered. `cost_delta_abs` measures the RE-SOLVE;
  // the card used to present it where a planner reads "what my move cost", which
  // is how two different gestures produced the same number to the cent. The
  // split block sits directly under the headline and names both parts.
  await boot(page);
  const mv = (await legalMoveTo(page, gesture.op, gesture.resource))
    || { resource_id: gesture.resource, start: gesture.start };
  await page.evaluate(([op, rid, start]) =>
    window.__cockpit.drag.dropAt(op, rid, start, /*altKey*/ true).then(() => {}),
    [gesture.op, mv.resource_id, mv.start]);
  await expect(page.locator(".delta-card.verdict")).toBeVisible();

  const rows = page.locator(".delta-card .dc-split .dc-split-row");
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toContainText("window re-optimization");
  await expect(rows.nth(1)).toContainText("your move");
  // exactly one row is the planner's own, and it is the emphasized one
  await expect(page.locator(".delta-card .dc-split-row.your-move")).toHaveCount(1);

  // the two drawn figures sum to the headline the card is showing (the same
  // decomposition-sums discipline the cost-by-line block already obeys)
  const money = async (loc) => {
    const t = (await loc.locator(".dc-split-v").innerText()).trim();
    return Number(t.replace(/[$,\s]/g, "").replace("−", "-").replace("+", ""));
  };
  const reopt = await money(rows.nth(0));
  const move = await money(rows.nth(1));
  const total = await page.evaluate(
    () => window.__cockpit.drag.state().result.cost_delta_abs);
  expect(Number((reopt + move).toFixed(2))).toBe(total);

  // and the unsplit fallback line is ABSENT when a real split is drawn
  await expect(page.locator(".delta-card .dc-split-note")).toHaveCount(0);
  await shot(page, "rolling_2beat_card_split");
});

test("CU2: the open card becomes ask context, and is CLEARED when it closes", async ({ page }) => {
  // The card is the top of the ask panel's resolution ladder while it is open —
  // and nothing at all once it is not. A stale card would answer confidently
  // about a move the planner can no longer see, which is worse than not
  // answering, so the clearing half is the load-bearing half of this test.
  await boot(page);
  const mv = (await legalMoveTo(page, gesture.op, gesture.resource))
    || { resource_id: gesture.resource, start: gesture.start };
  await page.evaluate(([op, rid, start]) =>
    window.__cockpit.drag.dropAt(op, rid, start, /*altKey*/ true).then(() => {}),
    [gesture.op, mv.resource_id, mv.start]);
  await expect(page.locator(".delta-card.verdict")).toBeVisible();

  const card = await page.evaluate(() => window.__cockpit.openCard);
  expect(card).toBeTruthy();
  expect(card.open).toBe(true);
  expect(card.operation_ref).toBe(gesture.op);
  // the payload is the CARD'S OWN CONTENT — the same numbers, not a second
  // derivation that could drift from the surface the planner is reading
  const shown = await page.evaluate(() => window.__cockpit.drag.state().result);
  expect(card.cost_delta_abs).toBe(shown.cost_delta_abs);
  expect(card.attribution).toBe(shown.attribution);
  expect(card.reopt_delta_abs).toBe(shown.reopt_delta_abs);
  expect(card.move_delta_abs).toBe(shown.move_delta_abs);
  // planner vocabulary, not canonical ids — the answer speaks the board's words
  expect(card.machine).toBeTruthy();
  expect(card.affected_orders).toBeTruthy();
  // and the panel is holding exactly it
  expect(await page.evaluate(() => window.__cockpit.panel.openCard().open)).toBe(true);

  // dismissed → the context is gone, in both places
  await page.locator(".delta-card .dc-discard").click();
  await expect(page.locator(".delta-card.hidden")).toHaveCount(1);
  expect(await page.evaluate(() => window.__cockpit.openCard)).toBeNull();
  expect(await page.evaluate(() => window.__cockpit.panel.openCard())).toBeNull();
});

test("R-T2 rolling: dropping an active op onto a COMMITTED slot is refused (contradiction)", async ({ page }) => {
  test.skip(!gesture.contra, "no forced contradiction captured for this fixture");
  await boot(page);
  const c = gesture.contra;
  const st = await page.evaluate(([op, rid, start]) =>
    window.__cockpit.drag.dropAt(op, rid, start, /*altKey*/ true)
      .then(() => window.__cockpit.drag.state()),
    [c.op, c.resource, c.start]);
  // beat one relaxed the frozen front (feasible); beat two held it (infeasible) →
  // the R-T2 contradiction, shown as a return-home rejection.
  expect(st.contradiction && st.contradiction.infeasible).toBe(true);
  await expect(page.locator(".delta-card.return-home")).toBeVisible();
  await shot(page, "rolling_2beat_contradiction");
});

test("R-T2 rolling: 'ask why' on the card bridges to a live grounded answer", async ({ page }) => {
  await boot(page);
  const mv = (await legalMoveTo(page, gesture.op, gesture.resource))
    || { resource_id: gesture.resource, start: gesture.start };
  await page.evaluate(([op, rid, start]) =>
    window.__cockpit.drag.dropAt(op, rid, start, /*altKey*/ true).then(() => {}),
    [gesture.op, mv.resource_id, mv.start]);
  await expect(page.locator(".delta-card.verdict")).toBeVisible();
  await page.locator(".delta-card .dc-askwhy").click();
  // CU4: the ask-why bridge composed a real "why is X on Y?" and the panel
  // answered it (the R-AI1 connector is retired) — an answer turn appears.
  await page.waitForFunction(
    () => !document.querySelector("#ask-log .empty")
       && !!document.querySelector("#ask-log pre"), { timeout: 10000 });
  await expect(page.locator("#ask-log")).toContainText("because");
  const ctx = await page.evaluate(() => window.__cockpit.drag.state().askWhyContext);
  expect(ctx && ctx.operation_ref).toBe(gesture.op);
  await shot(page, "rolling_2beat_askwhy");
});
