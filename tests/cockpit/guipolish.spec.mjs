// SESSION 4B.34 — GUI POLISH. The six items' guards, all driven THROUGH THE
// USER'S DOOR: real clicks on real controls, real pointer drags on real headers.
// 4B.28 §5a.123 is why — a control driven past its own entry point (there,
// `drag.grab()` instead of `onPointerDown`) stayed green against the very defect
// it was written for.
import { test, expect } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const SHOTS = resolve(dirname(fileURLToPath(import.meta.url)), "shots");
mkdirSync(SHOTS, { recursive: true });
const theme = () => test.info().project.metadata?.theme || "light";
const shot = (page, name) => page.screenshot({ path: resolve(SHOTS, `${name}__${theme()}.png`) });

const ROLLING = "sched-rolling-fixture";      // has all three docks
const PLANNER = "sched-planner-fixture";      // a different plant → different placements

async function boot(page, schedule = ROLLING) {
  await page.request.post("/__test__/reset").catch(() => {});
  await page.addInitScript(() => {
    try { localStorage.removeItem("mre-docks"); localStorage.removeItem("mre-view-mode");
          localStorage.removeItem("mre-compress"); } catch { /* private mode */ }
  });
  await page.goto(`/?schedule=${schedule}&theme=${theme()}`);
  await page.waitForFunction(() => window.__cockpit && window.__cockpit.ready === true,
                             { timeout: 20000 });
  await page.waitForFunction(() => document.querySelectorAll(".vis-item.bar").length > 0,
                             { timeout: 10000 });
}
const boxOf = (page, sel) => page.evaluate((s) => {
  const el = document.querySelector(s);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { x: r.x, y: r.y, w: r.width, h: r.height, right: r.right, bottom: r.bottom };
}, sel);
const intersects = (a, b) => !(a.right <= b.x || b.right <= a.x
                            || a.bottom <= b.y || b.bottom <= a.y);

// ======================================================================
// ITEM 1 + ITEM 4 — every dock reclaims its space, and its chevron says which
// way it went. ONE FAMILY, so a fourth dock inherits the guard by existing.
// ======================================================================

const DOCKS = [
  { key: "tray", sel: ".beyond-tray", axis: "y", grows: "h" },
  { key: "coarse", sel: ".coarse-band", axis: "y", grows: "h" },
  { key: "ask", sel: ".ask", axis: "x", grows: "w" },
];

for (const d of DOCKS) {
  test(`Item 1 — collapsing the ${d.key} dock gives the board its space (and expanding gives it back)`,
    async ({ page }) => {
      await boot(page);
      // every dock OPEN, through the docks' own API (the state under test is
      // what the EDGE BUTTON does, below).
      await page.evaluate(() => {
        for (const k of Object.keys(window.__cockpit.docks)) window.__cockpit.docks[k].set(true);
      });
      await page.waitForTimeout(400);
      const openBoard = await boxOf(page, "#tl");
      const openDock = await boxOf(page, d.sel);
      expect(openDock, `${d.key} dock is mounted`).not.toBeNull();

      // THE USER'S DOOR: a real click on the dock's own labelled edge.
      await page.click(`.dock-edge[data-dock="${d.key}"]`);
      await page.waitForTimeout(500);
      const shutBoard = await boxOf(page, "#tl");
      const shutDock = await boxOf(page, d.sel);

      // the dock shrank to its edge…
      expect(shutDock[d.grows], `${d.key} shrinks`).toBeLessThan(openDock[d.grows]);
      // …and the board grew by EXACTLY what it gave back. This is the assertion
      // that was false at HEAD: the tray and the coarse band carried a fixed
      // flex-basis, so they went on reserving their full height while showing an
      // edge, and #tl never moved at all.
      const freed = openDock[d.grows] - shutDock[d.grows];
      expect(shutBoard[d.grows] - openBoard[d.grows],
             `the board reclaims the ${d.key}'s ${freed}px`).toBeCloseTo(freed, 0);

      // and expanding restores it
      await page.click(`.dock-edge[data-dock="${d.key}"]`);
      await page.waitForTimeout(500);
      const backBoard = await boxOf(page, "#tl");
      expect(backBoard[d.grows], "restored").toBeCloseTo(openBoard[d.grows], 0);
    });

  test(`Item 4 — the ${d.key} chevron points along the axis it collapses`, async ({ page }) => {
    await boot(page);
    await page.evaluate((k) => window.__cockpit.docks[k].set(true), d.key);
    await page.waitForTimeout(300);
    const open = await page.evaluate((k) => window.__cockpit.docks[k].probe(), d.key);
    expect(open.axis, `${d.key} declares its axis`).toBe(d.axis);
    expect(open.chevron, "open").toBe(d.axis === "x" ? "right" : "down");
    await page.click(`.dock-edge[data-dock="${d.key}"]`);
    await page.waitForTimeout(300);
    const shut = await page.evaluate((k) => window.__cockpit.docks[k].probe(), d.key);
    // THE DEFECT: ask collapses SIDEWAYS and drew the vertical pair, promising a
    // fold downward that never came.
    expect(shut.chevron, "collapsed").toBe(d.axis === "x" ? "left" : "right");
    // the badge survives the collapse in every state (4B.28's cardinal rule,
    // re-asserted here because this family is where a fourth dock will land).
    expect(shut.label, "the collapsed edge still names itself").toBeTruthy();
  });
}

test("Item 1 — a collapsed dock still states its count (the collapse never hides work)",
  async ({ page }) => {
    await boot(page);
    await page.evaluate(() => window.__cockpit.docks.tray.set(false));
    await page.waitForTimeout(300);
    const p = await page.evaluate(() => window.__cockpit.docks.tray.probe());
    expect(p.open).toBe(false);
    expect(p.badge, "122-style count survives the collapse").toBeTruthy();
    await shot(page, "gp_item1_docks_collapsed");
  });

// ======================================================================
// ITEM 2 — the legend's home. THE RULE: it may never overlap interactive
// content at any viewport width the cockpit supports.
// ======================================================================

for (const width of [1540, 1100]) {
  test(`Item 2 — the legend overlaps nothing interactive at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await boot(page);
    // the occlusion case: every dock OPEN, so the tray chips and the coarse
    // cells are on screen at their full height.
    await page.evaluate(() => {
      for (const k of Object.keys(window.__cockpit.docks)) window.__cockpit.docks[k].set(true);
    });
    await page.waitForTimeout(500);
    const legend = await boxOf(page, ".legend");
    expect(legend, "legend rendered").not.toBeNull();
    for (const sel of [".beyond-tray .bt-body", ".coarse-band", "#tl .vis-foreground"]) {
      const other = await boxOf(page, sel);
      if (!other || !other.w) continue;
      expect(intersects(legend, other), `legend vs ${sel}`).toBe(false);
    }
    // and it does not cover a single BAR — the thing the planner is reading, and
    // what the old absolutely-positioned row sat on at every width measured.
    const barHits = await page.evaluate(() => {
      const l = document.querySelector(".legend").getBoundingClientRect();
      return [...document.querySelectorAll(".vis-item.bar")].filter((b) => {
        const r = b.getBoundingClientRect();
        return !(l.right <= r.x || r.right <= l.x || l.bottom <= r.y || r.bottom <= l.y);
      }).length;
    });
    expect(barHits, "bars under the legend").toBe(0);
    await shot(page, `gp_item2_legend_${width}`);
  });
}

// ======================================================================
// ITEM 3 — popups that hide what they describe.
// ======================================================================

test("Item 3(a) — a hover card never covers the bar it describes", async ({ page }) => {
  await boot(page);
  // EVERY bar, not a sample. Measured against the pre-fix placement, only 4 of
  // 366 bars actually ended up under their own card (worst overlap 556px²) —
  // a five-bar sample passed cleanly over the defect twice before this sweep
  // caught it. The occlusion needs a bar low enough that the card, offered at
  // pointer + (14,14), would leave the host and got flipped UP onto it.
  const bars = await page.evaluate(() => {
    const items = window.__cockpit.board.timeline.itemSet.items;
    return Object.keys(items).filter((k) => {
      const el = items[k].dom && items[k].dom.box;
      return el && el.getBoundingClientRect().width > 4;
    });
  });
  expect(bars.length, "bars to hover").toBeGreaterThan(20);
  const offenders = [];
  for (const id of bars) {
    const r = await page.evaluate((k) => {
      const b = window.__cockpit.board.timeline.itemSet.items[k].dom.box.getBoundingClientRect();
      return { x: b.x, y: b.y, w: b.width, h: b.height, right: b.right, bottom: b.bottom };
    }, id);
    // a REAL pointer move onto the bar's own middle
    await page.mouse.move(r.x + r.w / 2, r.y + r.h / 2);
    await page.waitForTimeout(40);
    const overlap = await page.evaluate((rr) => {
      const c = document.querySelector(".hover-card");
      if (!c || c.classList.contains("hidden")) return 0;
      const cr = c.getBoundingClientRect();
      const ox = Math.min(cr.right, rr.right) - Math.max(cr.x, rr.x);
      const oy = Math.min(cr.bottom, rr.bottom) - Math.max(cr.y, rr.y);
      return (ox > 0 && oy > 0) ? Math.round(ox * oy) : 0;
    }, r);
    if (overlap > 0) offenders.push({ y: Math.round(r.y), overlap });
  }
  expect(offenders, `cards sitting on their own bar: ${JSON.stringify(offenders.slice(0, 5))}`)
    .toEqual([]);
  await shot(page, "gp_item3_hovercard");
});

test("Item 3(b) — the job panel is dragged by its header and stays put across a refresh",
  async ({ page }) => {
    await boot(page);
    // open it the way a planner does: click a bar.
    await page.evaluate(() => {
      const d = window.__cockpit.doc;
      window.__cockpit.board.select(d.assignments[0].operation_ref);
    });
    await page.waitForTimeout(400);
    await expect(page.locator("#job-panel")).toBeVisible();
    const before = await boxOf(page, "#job-panel");
    const head = await boxOf(page, "#job-panel .jp-head");

    // THE USER'S DOOR: a real pointer drag on the header itself.
    await page.mouse.move(head.x + head.w / 2, head.y + head.h / 2);
    await page.mouse.down();
    await page.mouse.move(head.x + head.w / 2 - 260, head.y + head.h / 2 + 120, { steps: 12 });
    await page.mouse.up();
    await page.waitForTimeout(300);

    const after = await boxOf(page, "#job-panel");
    expect(Math.abs(after.x - before.x), "moved horizontally").toBeGreaterThan(100);
    expect(Math.abs(after.y - before.y), "moved vertically").toBeGreaterThan(40);
    const parked = await page.evaluate(() => window.__cockpit.jobPanel.probe().pos);
    expect(parked, "the placement is owned outside the rebuilt subtree").not.toBeNull();

    // A DATA REFRESH re-renders the panel's whole subtree. The placement must
    // survive it — the 4B.28 boundary-grip species: state in a node a redraw
    // recreates is state a redraw destroys.
    await page.evaluate(() => {
      const d = window.__cockpit.doc;
      window.__cockpit.board.select(d.assignments[0].operation_ref);
      window.__cockpit.jobPanel.show({ work_orders: d.assignments[0].work_orders,
                                       operation_ref: d.assignments[0].operation_ref });
    });
    await page.waitForTimeout(300);
    const afterRefresh = await boxOf(page, "#job-panel");
    expect(afterRefresh.x, "x survived the rebuild").toBeCloseTo(after.x, 0);
    expect(afterRefresh.y, "y survived the rebuild").toBeCloseTo(after.y, 0);
    await shot(page, "gp_item3_jobpanel_dragged");
  });

test("Item 3(b) — the ✕ still closes rather than starting a drag", async ({ page }) => {
  await boot(page);
  await page.evaluate(() => {
    const d = window.__cockpit.doc;
    window.__cockpit.board.select(d.assignments[0].operation_ref);
  });
  await page.waitForTimeout(400);
  await page.click("#job-panel .jp-close");
  await page.waitForTimeout(200);
  await expect(page.locator("#job-panel")).toBeHidden();
});

// ======================================================================
// ITEM 5 — the three-state view, and the label as a VIEW of the board's state.
// ======================================================================

const EXPECTED = [
  { mode: "linear", marks: 0, compressed: false, label: /linear/i },
  { mode: "folded", marks: "some", compressed: true, label: /compressed.*folds marked/i },
  { mode: "clean", marks: 0, compressed: true, label: /compressed.*clean/i },
];

test("Item 5(b) — the cycle is linear → folded → clean → linear, and the label discloses which",
  async ({ page }) => {
    await boot(page);
    const read = () => page.evaluate(() => ({
      mode: window.__cockpit.board.viewMode(),
      compressed: window.__cockpit.board.isCompressed(),
      hidden: (window.__cockpit.board.timeline.options.hiddenDates || []).length,
      marks: document.querySelectorAll(".fold-mark").length,
      label: document.querySelector("#board-compress").textContent,
      attr: document.querySelector("#board-compress").dataset.viewMode,
    }));
    expect((await read()).mode, "linear is the default — a folded ruler is not a scale anyone chose")
      .toBe("linear");
    // two full laps, so the cycle is proven to CYCLE and not merely to advance.
    for (let lap = 0; lap < 2; lap++) {
      for (let i = 1; i <= 3; i++) {
        await page.click("#board-compress");           // the user's door
        await page.waitForTimeout(450);
        const s = await read();
        const want = EXPECTED[i % 3];
        expect(s.mode, `lap ${lap} step ${i}`).toBe(want.mode);
        expect(s.attr, "the control names the active view").toBe(want.mode);
        expect(s.compressed).toBe(want.compressed);
        expect(s.label, "the label IS the disclosure").toMatch(want.label);
        // the AXIS mode: compression is vis's hiddenDates, and `clean` hides the
        // MARKS without un-hiding the dates — time is still missing, which is
        // exactly why the label may not be silent there.
        if (want.compressed) expect(s.hidden, "dates hidden").toBeGreaterThan(0);
        else expect(s.hidden, "linear hides nothing").toBe(0);
        if (want.marks === 0) expect(s.marks, `${want.mode} draws no fold marks`).toBe(0);
        else expect(s.marks, "folded marks every fold").toBeGreaterThan(0);
      }
    }
    await shot(page, "gp_item5_cycle");
  });

test("Item 5(a) — the view survives every redraw a planner can cause", async ({ page }) => {
  await boot(page);
  await page.click("#board-compress");                 // → folded
  await page.waitForTimeout(400);
  const read = () => page.evaluate(() => ({
    mode: window.__cockpit.board.viewMode(),
    hidden: (window.__cockpit.board.timeline.options.hiddenDates || []).length,
    label: document.querySelector("#board-compress").dataset.viewMode,
  }));
  const start = await read();
  expect(start.mode).toBe("folded");
  const shakes = {
    "zoom": () => page.click(".bz-in"),
    "dock collapse": () => page.click('.dock-edge[data-dock="tray"]'),
    "resize": () => page.setViewportSize({ width: 1200, height: 820 }),
    "resize back": () => page.setViewportSize({ width: 1540, height: 900 }),
    "rebind": () => page.evaluate(() => window.__cockpit.board.rebind(window.__cockpit.doc, {})),
  };
  for (const [name, fn] of Object.entries(shakes)) {
    await fn();
    await page.waitForTimeout(500);
    const s = await read();
    expect(s.mode, `mode survives ${name}`).toBe("folded");
    expect(s.hidden, `hidden dates survive ${name}`).toBe(start.hidden);
    expect(s.label, `the LABEL survives ${name}`).toBe("folded");
  }
});

test("Item 5(a) — the label is a VIEW of the board, not a copy the click handler wrote",
  async ({ page }) => {
    await boot(page);
    // Reaching compression by ANY route other than the button must repaint the
    // control. At HEAD the handler painted the label itself, so this left the
    // button reading "⇤ linear" over a compressed board — measured on the live
    // Khalil board before the fix.
    await page.evaluate(() => window.__cockpit.board.setViewMode("clean"));
    await page.waitForTimeout(400);
    const s = await page.evaluate(() => ({
      mode: window.__cockpit.board.viewMode(),
      attr: document.querySelector("#board-compress").dataset.viewMode,
      label: document.querySelector("#board-compress").textContent,
    }));
    expect(s.mode).toBe("clean");
    expect(s.attr, "the control followed a change it did not make").toBe("clean");
    expect(s.label).toMatch(/clean/i);
  });

// ======================================================================
// ITEM 6 — R-GP1 in the browser. The pure rule is in lineage.spec.mjs; this is
// the wiring: a real listing, a real fetch of each document, a real banner.
// ======================================================================

async function addChild(page, { id, base, parent, snapshot, created }) {
  await page.request.post("/__test__/add-schedule", {
    data: { id, base, parent_schedule_id: parent, snapshot_id: snapshot,
            created_at: created, status: "proposed" },
  });
}

test("Item 6 — an AUTHORITY-ONLY child never fires the newer-schedule banner",
  async ({ page }) => {
    await boot(page);
    // a ceremony child: newer row, SAME document (served from the same fixture
    // dir) → placement-identical, exactly like `rolling-b4dd3010751f`.
    await addChild(page, { id: "sched-rolling-fixture-thaw", base: ROLLING,
                           parent: ROLLING, snapshot: "snap-rolling",
                           created: "2030-01-01T00:00:00Z" });
    await page.evaluate(() => window.__cockpit.checkFreshness());
    await page.waitForTimeout(2500);
    await expect(page.locator("#newer-banner"), "no banner for a copy of this plan")
      .toHaveCount(0);
    const copies = await page.evaluate(() => window.__cockpit.freshnessCopies || []);
    expect(copies, "and the watch RAN and chose not to offer it")
      .toContain("sched-rolling-fixture-thaw");
  });

test("Item 6 — a RESUBMIT is not a copy, even with identical placements", async ({ page }) => {
  await boot(page);
  // The scope R-GP1 must NOT overreach past. This row serves the SAME document
  // (so its placement key matches exactly) but has NO parent — it is a fresh
  // solve of a re-uploaded submission, which is a different plan of record.
  // Suppressing it would strand a planner on a board they replaced; caught by
  // deeplink.spec.mjs's auto-follow guard when the comparison was unscoped.
  await addChild(page, { id: "sched-rolling-fixture-resubmit", base: ROLLING,
                         parent: null, snapshot: "snap-rolling",
                         created: "2030-01-01T00:00:00Z" });
  await page.evaluate(() => window.__cockpit.checkFreshness());
  await page.waitForTimeout(2500);
  const copies = await page.evaluate(() => window.__cockpit.freshnessCopies || []);
  expect(copies, "a non-descendant is never treated as a copy of this plan")
    .not.toContain("sched-rolling-fixture-resubmit");
  expect(await page.evaluate(() => window.__cockpit.newerId))
    .toBe("sched-rolling-fixture-resubmit");
});

test("Item 6 — a PLACEMENT-CHANGING child still fires the banner", async ({ page }) => {
  await boot(page);
  // a different plant's document → its placement key genuinely differs. The
  // premise is asserted below rather than assumed.
  await addChild(page, { id: "sched-rolling-fixture-moved", base: PLANNER,
                         parent: ROLLING, snapshot: "snap-edit-deadbeef",
                         created: "2030-01-01T00:00:00Z" });
  // (the premise that these two documents genuinely differ is asserted in its
  // own test below, against the same derivation the product uses)
  await page.evaluate(() => window.__cockpit.checkFreshness());
  await page.waitForTimeout(2500);
  await expect(page.locator("#newer-banner"), "a different plan DOES interrupt")
    .toHaveCount(1);
  const offered = await page.evaluate(() => window.__cockpit.newerId);
  expect(offered).toBe("sched-rolling-fixture-moved");
});

test("Item 6 — PREMISE: the two injected children really do differ in placements",
  async ({ page }) => {
    // If the 'moved' child were secretly placement-identical, the banner test
    // above would pass for the wrong reason. Compared here through the SAME
    // derivation the product uses, over the documents the server actually serves.
    await boot(page);
    await addChild(page, { id: "sched-rolling-fixture-thaw", base: ROLLING,
                           parent: ROLLING, snapshot: "snap-rolling",
                           created: "2030-01-01T00:00:00Z" });
    await addChild(page, { id: "sched-rolling-fixture-moved", base: PLANNER,
                           parent: ROLLING, snapshot: "snap-edit-deadbeef",
                           created: "2030-01-02T00:00:00Z" });
    const keys = await page.evaluate(async () => {
      const key = (d) => {
        const rows = (d.assignments || []).map((a) => `${a.operation_ref}|${a.resource_id}|`
          + (a.chunks || []).map((c) => `${c.start}~${c.end}`).sort().join(","));
        rows.sort();
        return `${rows.length}#${rows.join("\n")}`;
      };
      const get = async (id) => {
        const r = await (await fetch(`/schedules/${id}`)).json();
        const d = r.data && (r.data.document || r.data);
        return key(d);
      };
      return {
        parent: await get("sched-rolling-fixture"),
        thaw: await get("sched-rolling-fixture-thaw"),
        moved: await get("sched-rolling-fixture-moved"),
      };
    });
    expect(keys.thaw, "the authority-only child IS placement-identical").toBe(keys.parent);
    expect(keys.moved, "the moved child IS placement-different").not.toBe(keys.parent);
  });

test("Item 6 — the picker row names the badge, and CURRENT stays on the plan-bearing row",
  async ({ page }) => {
    await boot(page);
    await addChild(page, { id: "sched-rolling-fixture-thaw", base: ROLLING,
                           parent: ROLLING, snapshot: "snap-rolling",
                           created: "2030-01-01T00:00:00Z" });
    await page.click("#sched-ident");
    await page.waitForSelector(".sl-row", { timeout: 10000 });
    await page.waitForFunction(
      () => document.querySelector('.sl-row[data-plan-current]') != null, { timeout: 20000 });
    const rows = await page.evaluate(() => [...document.querySelectorAll(".sl-row")].map((r) => ({
      id: r.dataset.scheduleId, badge: r.dataset.badge || null,
      planCurrent: r.dataset.planCurrent === "true",
      digest: r.dataset.planDigest || null,
      facts: (r.querySelector(".sl-facts") || {}).textContent || "",
    })));
    const thaw = rows.find((r) => r.id === "sched-rolling-fixture-thaw");
    const parent = rows.find((r) => r.id === ROLLING);
    expect(thaw, "the child is listed — shown in the lineage, never hidden").toBeTruthy();
    expect(thaw.badge, "and named for what it is").toBe("authority-only");
    expect(thaw.digest, "carrying the plan digest that proves it").toBe(parent.digest);
    // THE RULING: the newest ROW is not the CURRENT PLAN.
    expect(thaw.planCurrent, "a copy never leads the lineage").toBe(false);
    expect(parent.planCurrent, "the board it copies does").toBe(true);
    // and the row states the derived facts a planner needs to tell them apart
    expect(parent.facts, "bar count").toMatch(/\d+ bars/);
    await shot(page, "gp_item6_picker");
  });
