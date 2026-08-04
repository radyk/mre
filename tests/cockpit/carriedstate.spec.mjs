// R-MT1's CLIENT HALF, in a real browser (Session 4A teaching-graft (d.1)).
//
// The (d.0) recon proved the SERVER half of D-05 in-process — `ANSWER_MEMORY`,
// `SYNTHESIS_MEMORY` and `_DELIVERED` keyed by session id alone, so a prove-it
// after an in-place version rebind served 102 of board A's record ids to a
// planner looking at board B. It could NOT prove the gesture that reaches it:
// no probe drove Chrome, and the claim that `main.js::onVersionChange` leaves
// the ask panel's carried state intact was labelled an INFERENCE from
// `main.js:745-754` + `askpanel.js:419`.
//
// This spec is that measurement. It drives the SHIPPED cockpit through a real
// accept — the same `drag.accept()` gesture `gesture.spec.mjs` uses — and reads
// what the NEXT /ask request actually carries. The assertions here are the
// AFTER (R-MT1 clause 2: a rebind clears the carried answer state); the BEFORE
// is recorded in the close-out, measured with this same file.
//
// Why the fixture harness rather than the live API: the gesture is a client
// one, and the client half is the whole question. The fixture server mints a
// real child version and `onVersionChange` fires for real; nothing about the
// carried-state question needs a solver.
import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const theme = () => test.info().project.metadata?.theme || "light";

const SCHEDULE = "sched-multi-route-distinct";
const DIST = resolve(HERE, "fixtures", "distinct");
const load = (n) => JSON.parse(readFileSync(resolve(DIST, n), "utf-8"));
const sandbox = load("sandbox.json");
const byOp = sandbox.by_op;
const opFor = (outcome) => Object.keys(byOp).find((op) => byOp[op].outcome === outcome);

// The one canned question this fixture answers. Any question is enough to put a
// turn in `askHistory`; what this spec reads is what the NEXT request carries.
const Q1 = "why is ORD-000003 on F001-RES001?";
const Q2 = "show me the evidence for that";

async function boot(page) {
  await page.request.post("/__test__/reset").catch(() => {});
  await page.goto(`/?schedule=${SCHEDULE}&theme=${theme()}`);
  await page.waitForFunction(() => window.__cockpit && window.__cockpit.ready === true, { timeout: 20000 });
  await page.waitForFunction(() => document.querySelectorAll(".vis-item.bar").length > 0, { timeout: 10000 });
  await page.waitForFunction(() => window.__cockpit.drag && window.__cockpit.alternativesReady === true, { timeout: 10000 });
}

// A genuine legal MOVE for an op, copied in shape from gesture.spec.mjs: a
// Tier-0-legal start on the incumbent machine, well clear of the incumbent
// placement (R-DP9 makes dropping AT the incumbent a no-op).
async function legalMove(page, op) {
  const mv = await page.evaluate((op) => {
    const d = window.__cockpit.drag;
    const a = window.__cockpit.doc.assignments.find((x) => x.operation_ref === op);
    const rid = a.resource_id, inc = Date.parse(a.chunks[0].start);
    const row = (d.tier0For(op).rows || []).find((r) => r.resource_id === rid);
    const ghosts = d.ghostsFor(op).filter((g) => g.resource_id === rid).map((g) => Date.parse(g.start));
    const MIN = 60000, FAR = 120 * MIN;
    const nearGhost = (t) => ghosts.some((g) => Math.abs(g - t) < 30 * MIN);
    for (const reg of (row && row.legal_regions) || []) {
      const s = Date.parse(reg.start), e = Date.parse(reg.end);
      for (const cand of [s, s + FAR, e - FAR, e]) {
        if (cand < s || cand > e) continue;
        if (Math.abs(cand - inc) < FAR) continue;
        if (nearGhost(cand)) continue;
        return { resource_id: rid, start: new Date(cand).toISOString() };
      }
    }
    return null;
  }, op);
  if (!mv) throw new Error(`no legal move found for ${op}`);
  return mv;
}

/** Ask, and return the request body the panel sent. */
async function askAndCapture(page, question) {
  const req = page.waitForRequest(
    (r) => /\/ask$/.test(new URL(r.url()).pathname) && r.method() === "POST",
    { timeout: 15000 });
  await page.evaluate((q) => window.__cockpit.ask(q), question);
  const r = await req;
  return { url: new URL(r.url()).pathname, body: r.postDataJSON() };
}

test("an in-place version rebind CLEARS the carried answer state (R-MT1 clause 2)", async ({ page }) => {
  await boot(page);

  // Turn 1 on the parent board — a real answer, so `askHistory` gains a turn
  // and `lastAnswered` is written (askpanel.js:272, 283).
  const first = await askAndCapture(page, Q1);
  await expect(page.locator(".msg.answer")).toBeVisible();
  expect(first.body.session_id, "the panel sends a session id").toBeTruthy();
  expect(first.url).toContain(SCHEDULE);
  const parentSession = first.body.session_id;

  const turns = await page.evaluate(() => window.__cockpit.panel.turnCount());
  expect(turns, "turn 1 is in the panel's history").toBe(1);

  // THE GESTURE. A real drag → verdict → accept, which mints a child version and
  // calls `onVersionChange`: the same seam an accepted edit, a boundary move and
  // a publish all land on.
  const op = opFor("verdict");
  const mv = await legalMove(page, op);
  const v = await page.evaluate(([op, rid, start]) =>
    window.__cockpit.drag.dropAt(op, rid, start, /*altKey*/ true).then(() => window.__cockpit.drag.state()),
    [op, mv.resource_id, mv.start]);
  expect(v.phase, "the drop priced a verdict to accept").toBe("verdict");
  const acc = await page.evaluate(() => window.__cockpit.drag.accept().then(() => ({
    scheduleId: window.__cockpit.scheduleId,
    changed: window.__cockpit.versionChanged,
  })));
  expect(acc.changed, "the accept fired onVersionChange").toBeTruthy();
  expect(acc.scheduleId, "the cockpit rebound to the child").not.toBe(SCHEDULE);

  // THE MEASUREMENT. What does the next question carry?
  const second = await askAndCapture(page, Q2);

  // (i) it is asked against the CHILD — the rebind happened.
  expect(second.url, "the next ask goes to the new version").toContain(acc.scheduleId);
  expect(acc.scheduleId, "the child is a different id").not.toBe(SCHEDULE);
  // The BEFORE, recorded where a reader of a failing run will see it.
  test.info().annotations.push({
    type: "carried", description: JSON.stringify({
      url: second.url, session_id: second.body.session_id,
      history: second.body.history,
      last_answered_subject: second.body.last_answered_subject }),
  });

  // (ii) R-MT1 clause 2 — THE CARRIED ANSWER STATE IS GONE. Before this session
  // both of these carried the parent board's turn across the boundary, which is
  // the client half of D-05.
  expect(second.body.history, "the rebind cleared the conversation history")
    .toEqual([]);
  expect(second.body.last_answered_subject || {},
    "the rebind cleared the last-answered subject").toEqual({});

  // (iii) the session id SURVIVES, deliberately. Once the server's three stores
  // key on (session, schedule) — R-MT1 clause 1 — a surviving session id can
  // reach nothing from the parent board, and minting a new one on every accept
  // would fragment the question ledger's own session thread (R-AI5(5)).
  expect(second.body.session_id, "the session id is not re-minted by a rebind")
    .toBe(parentSession);
});

test("the schedule PICKER path is a full reload and stays that way", async ({ page }) => {
  await boot(page);
  const first = await askAndCapture(page, Q1);
  await expect(page.locator(".msg.answer")).toBeVisible();

  // `jumpToVersion` is a `location.assign`, so the panel — session id, history
  // and all — is rebuilt from scratch. Asserted rather than assumed: the recon
  // called this path safe and the client half of R-MT1 must not change it.
  await page.goto(`/?schedule=${SCHEDULE}&theme=${theme()}`);
  await page.waitForFunction(() => window.__cockpit && window.__cockpit.ready === true, { timeout: 20000 });
  const second = await askAndCapture(page, Q1);
  expect(second.body.history, "a reload starts an empty conversation").toEqual([]);
  expect(second.body.session_id, "a reload mints a new session id")
    .not.toBe(first.body.session_id);
});
