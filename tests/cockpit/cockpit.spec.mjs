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
// Theme is a harness dimension (4.1 CU3): the active theme comes from the
// Playwright project's metadata; every boot renders in it and screenshots are
// suffixed by it so light + dark captures coexist (shots/ is gitignored).
const theme = () => test.info().project.metadata?.theme || "light";
const themeParam = () => `&theme=${theme()}`;
const shot = (page, name) => page.screenshot({ path: resolve(SHOTS, `${name}__${theme()}.png`) });

const SCHEDULE = "sched-multi-route-fixture";
const ACCEPTANCE_Q = "why is ORD-000012 on F001-RES001?";
const JUDGMENT_Q = "what data problems exist?";
const DRIFT_MAX_PX = 1.0;      // 0.0 expected; allow sub-pixel rounding

async function boot(page, extra = "") {
  await page.request.post("/__test__/reset").catch(() => {});  // clean lifecycle (3.8)
  await page.goto(`/?schedule=${SCHEDULE}${themeParam()}${extra}`);
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

test("resolved question — an elliptical follow-up shows what it answered (CU2)", async ({ page }) => {
  await boot(page);
  // the server (here the fixture) resolved "and what about it?" against the prior
  // subject and returned resolved_question; the panel surfaces it before the
  // answer (the deictic pattern from 3.2d, generalized, R-AI1 CU2).
  await page.evaluate(() => window.__cockpit.ask("and what about it?"));
  const note = page.locator(".msg.resolved-note").last();
  await expect(note).toBeVisible();
  await expect(note.locator("pre")).toHaveText("why is ORD-000012 late?");
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

test("theme — light is the shipped default; the toggle flips attribute + palette (4.1)", async ({ page }) => {
  // Boot WITHOUT any theme param (fresh, isolated context → no stored pref): the
  // shipped default must be light. This is theme-independent, so it asserts the
  // same thing under both projects.
  await page.request.post("/__test__/reset").catch(() => {});
  await page.goto(`/?schedule=${SCHEDULE}`);
  await page.waitForFunction(() => window.__cockpit && window.__cockpit.ready === true, { timeout: 20000 });
  expect(await page.evaluate(() => document.documentElement.getAttribute("data-theme"))).toBe("light");

  const bgHex = () => page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue("--bg").trim());
  const lum = (hex) => { const m = hex.match(/[0-9a-f]{2}/gi).map((h) => parseInt(h, 16)); return 0.299 * m[0] + 0.587 * m[1] + 0.114 * m[2]; };
  const lightBg = await bgHex();

  // the chrome toggle exists and is labelled with an accessible name
  const toggle = page.locator("#theme-toggle");
  await expect(toggle).toBeVisible();
  expect(await toggle.getAttribute("aria-label")).toMatch(/theme: light/i);

  // toggle → dark: attribute flips, the palette is a DIFFERENT design (paper
  // gives way to a genuinely dark base, not a tint)
  await toggle.click();
  expect(await page.evaluate(() => document.documentElement.getAttribute("data-theme"))).toBe("dark");
  const darkBg = await bgHex();
  expect(darkBg).not.toBe(lightBg);
  expect(lum(lightBg), "light paper far brighter than the dark base").toBeGreaterThan(lum(darkBg) + 100);
  // the URL now carries the chosen theme (a shareable, reload-stable choice)
  expect(page.url()).toMatch(/theme=dark/);
  await shot(page, "08_theme_toggle");
});

// --- Session 4.3 riders ----------------------------------------------------

// CU1: the question-ledger dock and the legend share ONE structural chrome row —
// nothing may occlude the legend or the ask column at any width (the SECOND
// occlusion incident). The harness serves the production build (no auto-mount),
// so it mounts the REAL dev ledger via the harness seam, expands it, and asserts
// bounding-box non-intersection at two widths.
test("CU1 — the ledger dock never occludes the legend or ask column (two widths)", async ({ page }) => {
  await boot(page);
  await page.evaluate(() => window.__cockpit.mountDevLedger());
  await expect(page.locator(".dev-ledger")).toBeVisible();
  await expect(page.locator(".legend")).toBeVisible();
  await page.locator(".dev-ledger .dl-toggle").click();   // expand → body drops UP over board
  await expect(page.locator(".dev-ledger .dl-body")).toBeVisible();

  const rects = () => page.evaluate(() => {
    const box = (sel) => { const el = document.querySelector(sel); if (!el) return null;
      const r = el.getBoundingClientRect(); return { left: r.left, top: r.top, right: r.right, bottom: r.bottom }; };
    return { legend: box(".legend"), ledger: box(".dev-ledger"),
      body: box(".dev-ledger .dl-body"), ask: box(".ask") };
  });
  const overlap = (a, b) => !!a && !!b && a.left < b.right - 0.5 && b.left < a.right - 0.5
    && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5;

  for (const [w, h] of [[1540, 900], [1100, 780]]) {
    await page.setViewportSize({ width: w, height: h });
    await page.waitForTimeout(120);
    const R = await rects();
    expect(R.legend, `legend present @${w}`).not.toBeNull();
    expect(R.ledger, `ledger present @${w}`).not.toBeNull();
    expect(overlap(R.ledger, R.legend), `ledger tab vs legend @${w}`).toBe(false);
    expect(overlap(R.body, R.legend), `ledger body vs legend @${w}`).toBe(false);
    expect(overlap(R.ledger, R.ask), `ledger tab vs ask @${w}`).toBe(false);
    expect(overlap(R.body, R.ask), `ledger body vs ask @${w}`).toBe(false);
  }
  await shot(page, "09_ledger_chrome");
});

// CU5: the +/− zoom controls give a pointer/keyboard zoom path; a first-load hint
// names the Ctrl+scroll gesture.
test("CU5 — zoom controls change the window; the first-load hint is present", async ({ page }) => {
  await boot(page);
  await expect(page.locator("#board-hint")).toContainText("Ctrl+scroll to zoom");
  await expect(page.locator(".board-zoom .bz-in")).toBeVisible();
  await expect(page.locator(".board-zoom .bz-out")).toBeVisible();

  const span = async () => page.evaluate(() => {
    const w = window.__cockpit.getWindow();
    return Date.parse(w.end) - Date.parse(w.start);
  });
  const s0 = await span();
  await page.locator(".board-zoom .bz-in").click();
  await page.waitForTimeout(150);
  const s1 = await span();
  expect(s1, "zoom in narrows the window").toBeLessThan(s0);
  await page.locator(".board-zoom .bz-out").click();
  await page.locator(".board-zoom .bz-out").click();
  await page.waitForTimeout(150);
  expect(await span(), "zoom out widens it again").toBeGreaterThan(s1);
});

// CU6: on a current version no "newer schedule" banner appears (the positive
// path is pinned in freshness.spec.mjs; here we prove the wiring doesn't
// false-positive on a normal boot). Session 4.4: also proves no spurious
// auto-follow — the static fixtures tie on created_at, so none is "newer".
test("CU6 — no newer-schedule banner (and no auto-follow) when the bound version is current", async ({ page }) => {
  await boot(page);
  const before = page.url();
  await page.waitForTimeout(300);   // the freshness check is background work
  expect(await page.locator("#newer-banner").count()).toBe(0);
  expect(await page.locator("#followed-toast").count()).toBe(0);
  expect(page.url(), "no spurious auto-follow on a normal boot").toBe(before);
});

// --- Session 4.4: schedule freshness done right ----------------------------
// Inject a newer schedule into the data-root listing (a resubmit landing while
// the tab is bound to an older solve), then drive the freshness watch.
const injectNewer = (page, id, created_at = "2026-01-05T12:00:00Z") =>
  page.request.post("/__test__/add-schedule", {
    data: { id, base: "sched-multi-route-distinct", created_at, generation: 4 },
  });

// CU2 — the real fix: with NO uncommitted state, a newer schedule appearing while
// viewing auto-follows (reloads onto the new version) and confirms with a toast
// that offers a one-click way back.
test("CU2 — resubmit while viewing auto-follows to the newer schedule", async ({ page }) => {
  await boot(page);
  const NEWER = "sched-newer-autofollow";
  await injectNewer(page, NEWER);
  await page.evaluate(() => { window.__cockpit.checkFreshness(); return true; });
  await page.waitForURL((u) => new URL(u).searchParams.get("schedule") === NEWER, { timeout: 10000 });
  await page.waitForFunction(() => window.__cockpit && window.__cockpit.ready === true, { timeout: 20000 });
  // landed on the new version; the toast confirms the switch + offers back.
  await expect(page.locator("#followed-toast")).toBeVisible();
  await expect(page.locator("#followed-toast")).toContainText("Switched to the new schedule");
  await expect(page.locator("#ft-back")).toContainText("View previous");
  // one click back returns to the previous version (and never re-follows it).
  await page.locator("#ft-back").click();
  await page.waitForURL((u) => new URL(u).searchParams.get("schedule") === SCHEDULE, { timeout: 10000 });
});

// CU2 — uncommitted user state (here: a live bar selection = a pinned deictic
// scope) outranks freshness: the banner is offered, the board is NEVER yanked.
test("CU2 — uncommitted state shows the banner, never auto-switches", async ({ page }) => {
  await boot(page);
  await page.evaluate(() => {
    const op = window.__cockpit.doc.assignments[0].operation_ref;
    window.__cockpit.select(op);
  });
  expect(await page.evaluate(() => window.__cockpit.panel.hasUserState())).toBe(true);
  const before = page.url();
  await injectNewer(page, "sched-newer-blocked");
  await page.evaluate(() => { window.__cockpit.checkFreshness(); return true; });
  await page.waitForTimeout(400);
  expect(page.url(), "no auto-switch with uncommitted state").toBe(before);
  await expect(page.locator("#newer-banner")).toBeVisible();
  await expect(page.locator("#newer-banner")).toContainText("A newer schedule exists");
  expect(await page.locator("#followed-toast").count()).toBe(0);
});

// CU2 — a window focus rechecks freshness: the exact moment a planner returns
// from Excel after a data fix.
test("CU2 — a window focus rechecks freshness and follows", async ({ page }) => {
  await boot(page);
  const NEWER = "sched-newer-onfocus";
  await injectNewer(page, NEWER);
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await page.waitForURL((u) => new URL(u).searchParams.get("schedule") === NEWER, { timeout: 10000 });
  expect(new URL(page.url()).searchParams.get("schedule")).toBe(NEWER);
});

// CU3 — the top strip carries a human-scale identity (generation + clock), not
// just the hex, so two visually-similar boards are distinguishable at a glance.
test("CU3 — the top strip shows a human-scale schedule identity", async ({ page }) => {
  await boot(page);
  const ver = await page.locator(".topstrip .ver").innerText();
  expect(ver).toContain("contract 1.3");
  expect(ver, "generation counter is shown").toMatch(/solve #\d+/);
  expect(ver, "a clock time accompanies it").toMatch(/\d{2}:\d{2}/);
  await expect(page.locator(".topstrip .sched-ident")).toBeVisible();
});

// CU7: temporally-adjacent bars must read as DISTINCT at coarse (day) zoom —
// packed must never look overlapping. Each bar carries a seam; no two bars on a
// row truly overlap.
test("CU7 — packed bars read as distinct at day zoom (seam present, no overlap)", async ({ page }) => {
  await boot(page);
  // zoom to ~1 day on the busy multi_route rows (F001-RES001 packs 12 bars).
  await page.evaluate(() => window.__cockpit.setWindow("2026-01-05T06:00:00Z", "2026-01-06T06:00:00Z"));
  await page.waitForTimeout(150);
  // the CU7 separating seam (an inset box-shadow) is present on bars.
  const shadow = await page.locator(".vis-item.bar").first().evaluate((el) => getComputedStyle(el).boxShadow);
  expect(shadow, "bars carry a seam box-shadow").toContain("inset");
  // and no two bars on the same row actually OVERLAP (touching is fine; the seam
  // separates them visually — a >1px overlap would read as one merged bar).
  const overlaps = await page.evaluate(() => {
    const bars = [...document.querySelectorAll(".vis-item.bar")]
      .map((el) => el.getBoundingClientRect()).filter((r) => r.width > 0)
      .sort((a, b) => a.top - b.top || a.left - b.left);
    let bad = 0;
    for (let i = 1; i < bars.length; i++) {
      const a = bars[i - 1], b = bars[i];
      if (Math.abs(a.top - b.top) < 3 && b.left < a.right - 1) bad++;
    }
    return bad;
  });
  expect(overlaps, "no two adjacent bars overlap at day zoom").toBe(0);
  await shot(page, "10_packed_day_zoom");
});
