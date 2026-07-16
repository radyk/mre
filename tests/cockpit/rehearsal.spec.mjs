// The sixty-second rehearsal (docs/07 Phase 3 CU5) — the exit-demo script driven
// end to end, BEAT BY BEAT, screenshot-asserted, with the latency of each beat
// recorded to shots/rehearsal_report.json. This is the session's real
// deliverable: proof the whole arc holds as one continuous session.
//
// The script (docs/07 Phase 3 "The demo script"):
//   1. ask why an order is on its machine (VOICE) → sourced answer, bars glow
//   2. "what are my options" → priced ghosts appear on a grab
//   3. drag onto one → delta card (verdict) with the moved-set traced
//   4. Accept → a new proposed version; Publish → it supersedes the base
//   5. "summarize my changes" (VOICE) → sourced narrative citing the edit
//
// Hermetic: the fixture server stands in for the API (canned ask + ghosts +
// sandbox + accept/publish + a synthesized edit narrative). The REAL edit-domain
// answer + accept→Decision→publish are proven against the live API by the Python
// tests (test_planner_edit, test_edit_question_domain). Voice has no microphone
// in headless, so the spoken path is driven via panel.askSpoken (same route,
// spoken=true) and the "never voice record ids" contract is asserted in
// gesture.spec.
import { test, expect } from "@playwright/test";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SHOTS = resolve(HERE, "shots");
mkdirSync(SHOTS, { recursive: true });
const shot = (page, name) => page.screenshot({ path: resolve(SHOTS, `${name}.png`) });

const SCHEDULE = "sched-multi-route-distinct";
const DIST = resolve(HERE, "fixtures", "distinct");
const load = (n) => JSON.parse(readFileSync(resolve(DIST, n), "utf-8"));

const asks = load("asks.json");
const alternatives = load("alternatives.json");
const sandbox = load("sandbox.json");
const schedule = load("schedule.json");

// incumbent row of an op (for the 4.0 R-DP1 cross-machine end-state check).
function incumbent(opRef) {
  const a = schedule.assignments.find((x) => x.operation_ref === opRef);
  return a ? { resource_id: a.resource_id, start: a.chunks[0].start } : null;
}

const DEMO_Q = Object.keys(asks)[0];   // "why is ORD-000003 on F001-RES001?"
const priced = alternatives.members.filter((m) => m.verdict === "priced" && m.label.placement);
const opFor = (outcome) =>
  Object.keys(sandbox.by_op).find((op) => sandbox.by_op[op].outcome === outcome);

async function boot(page) {
  await page.request.post("/__test__/reset").catch(() => {});  // clean lifecycle (3.8)
  await page.goto(`/?schedule=${SCHEDULE}`);
  await page.waitForFunction(() => window.__cockpit && window.__cockpit.ready === true, { timeout: 20000 });
  expect(await page.evaluate(() => window.__cockpit.error || null)).toBeNull();
  await page.waitForFunction(() => document.querySelectorAll(".vis-item.bar").length > 0, { timeout: 10000 });
  await page.waitForFunction(() => window.__cockpit.drag && window.__cockpit.alternativesReady === true, { timeout: 10000 });
}

test("the sixty-second script, end to end (CU5 rehearsal)", async ({ page }) => {
  const report = { schedule: SCHEDULE, beats: [] };
  const beat = (name, ms, extra = {}) => report.beats.push({ name, ms: ms == null ? null : +ms.toFixed(1), ...extra });
  await boot(page);
  await shot(page, "r00_board");

  // --- Beat 1: ask (voice) why an order is on its machine → bars glow --------
  const t1 = Date.now();
  const b1 = await page.evaluate((q) => window.__cockpit.panel.askSpoken(q).then(() => ({
    litBars: document.querySelectorAll(".vis-item.bar.cited").length,
    answered: !!document.querySelector(".msg.answer.testimony"),
  })), DEMO_Q);
  expect(b1.answered, "a testimony answer landed").toBe(true);
  expect(b1.litBars, "the answer's cited bars glow").toBeGreaterThan(0);
  beat("ask_why_voice", Date.now() - t1, { litBars: b1.litBars });
  await shot(page, "r01_ask_bars_glow");

  // --- Beat 2: "what are my options" → priced ghosts on a grab --------------
  const g8 = priced[0].label.target_operation_ref;
  const t2 = Date.now();
  const b2 = await page.evaluate((op) => {
    window.__cockpit.drag.grab(op);
    const s = window.__cockpit.drag.state();
    return { ghosts: s.ghosts.length, grabToShadeMs: s.grabToShadeMs, priced: s.ghosts.filter((g) => g.delta_pct != null).length };
  }, g8);
  expect(b2.ghosts, "priced ghosts appear for the grabbed op").toBeGreaterThan(0);
  beat("options_ghosts", Date.now() - t2, { ghosts: b2.ghosts, grabToShadeMs: b2.grabToShadeMs });
  await shot(page, "r02_ghosts");
  await page.evaluate(() => window.__cockpit.drag.discard());

  // --- Beat 3: drag onto a ghost → verdict card + traced moved-set ----------
  const g = priced[0];
  const t3 = Date.now();
  const b3 = await page.evaluate(([op, rid, start]) =>
    window.__cockpit.drag.dropAt(op, rid, start).then(() => window.__cockpit.drag.state()),
    [g.label.target_operation_ref, g.label.placement.resource_id, g.label.placement.start]);
  expect(b3.phase, "the drop yields a verdict").toBe("verdict");
  expect(b3.traces, "the moved-set is traced old→new").toBeGreaterThan(0);
  await expect(page.locator(".delta-card .dc-outcome")).toBeVisible();
  beat("drag_verdict", Date.now() - t3, { dropToVerdictMs: b3.dropToVerdictMs, traces: b3.traces });
  await shot(page, "r03_verdict_card");

  // --- Beat 4: Accept → a new proposed version, then Publish ----------------
  // Beat 3 dropped op g onto a CROSS-machine ghost, so the accepted bar must
  // render on the PINNED row (g.placement.resource_id), never snap back to its
  // incumbent (4.0 R-DP1 end-state check — the demo script itself catches the
  // silent-machine-pin-skip regression).
  const home4 = incumbent(g.label.target_operation_ref).resource_id;
  const target4 = g.label.placement.resource_id;
  expect(target4, "beat 3 was a genuine cross-machine drop").not.toBe(home4);
  const t4 = Date.now();
  const acc = await page.evaluate(() => window.__cockpit.drag.accept().then(() => ({
    state: window.__cockpit.drag.state(), changed: window.__cockpit.versionChanged,
    placement: window.__cockpit.board.placementOf(window.__cockpit.drag.state().op),
  })));
  expect(acc.state.phase, "accept mints a new proposed version").toBe("accepted");
  expect(acc.changed.status).toBe("proposed");
  expect(acc.placement.group, "R-DP1: accepted bar on the pinned machine").toBe(target4);
  expect(acc.placement.group).not.toBe(home4);
  await expect(page.locator(".delta-card.accepted")).toBeVisible();
  await shot(page, "r04_accepted");
  const pub = await page.evaluate(() => window.__cockpit.drag.publish().then(() => ({
    state: window.__cockpit.drag.state(), changed: window.__cockpit.versionChanged,
  })));
  expect(pub.state.phase, "publish makes it the schedule of record").toBe("published");
  expect(pub.changed.status).toBe("published");
  await expect(page.locator("#topstrip .status")).toContainText("published");
  beat("accept_publish", Date.now() - t4, { acceptToDoneMs: acc.state.acceptToDoneMs });
  await shot(page, "r05_published");

  // --- Beat 5: "summarize my changes" (voice) → sourced narrative -----------
  const t5 = Date.now();
  const b5 = await page.evaluate(() =>
    window.__cockpit.panel.askSpoken("summarize what I changed and what it cost").then(() => {
      const answers = [...document.querySelectorAll(".msg.answer.testimony pre")];
      return { text: answers.length ? answers[answers.length - 1].textContent : "" };
    }));
  expect(b5.text.toLowerCase(), "the closing narrative names the edit").toContain("edit");
  expect(b5.text.toLowerCase()).toContain("dev-planner");
  beat("summarize_changes_voice", Date.now() - t5);
  await shot(page, "r06_summarize");

  // --- the rehearsal report -------------------------------------------------
  report.total_ms = report.beats.reduce((s, b) => s + (b.ms || 0), 0);
  writeFileSync(resolve(SHOTS, "rehearsal_report.json"), JSON.stringify(report, null, 2));
  // every beat produced a state (no silent stall)
  expect(report.beats.length).toBe(5);
  for (const b of report.beats) expect(b.ms, `${b.name} recorded a latency`).not.toBeNull();
});
