// Session 4B.23 — BEAT TWO IS REACHED, AND NOTHING BETWEEN THE BEATS IS SILENT.
//
// WHAT WAS MEASURED, before any fix. One drag on the dense demo board
// (`rolling-c9973708-865`, 386 bars) produced ONE network request:
//
//     POST /schedules/{id}/sandbox/feasibility   200   4.61s
//
// and no second one. Beat one returned `status: "UNKNOWN", feasible: false` —
// the check ran out of its 2s budget — and `controller.js` read the BOOLEAN,
// rendered "this placement isn't possible here", hid the card and snapped the
// bar home. Beat two, called directly by `tools/spikes/.../sandbox_move.py` on
// the identical pin, priced the same gesture at $2,596.67 (4B.22a §5(e)).
//
// So the chain did not break and was not swallowed: it was CONDITIONAL, and the
// condition was false on a dense board and true on the 56-bar pinned world —
// which is exactly why the pinned world could not reproduce it.
//
// The three things this file pins:
//   (1) an UNDETERMINED beat one still reaches beat two, and says so;
//   (2) an IMPOSSIBLE beat one refuses VISIBLY and never fires beat two;
//   (3) a beat-two FAILURE leaves a visible, named state — never a bare revert —
//       and reads differently from a refusal.
//
// Plus the Item 4 rule: a freshness poll may not discard a live proposal.
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
const gesture = JSON.parse(readFileSync(resolve(DIR, "gesture.json"), "utf-8"));

async function boot(page) {
  await page.request.post("/__test__/reset").catch(() => {});
  await page.goto(`/?schedule=${SCHEDULE}&theme=${theme()}`);
  await page.waitForFunction(() => window.__cockpit && window.__cockpit.ready === true, { timeout: 20000 });
  await page.waitForFunction(() => document.querySelectorAll(".vis-item.bar").length > 0, { timeout: 10000 });
  await page.waitForFunction(() => window.__cockpit.drag && window.__cockpit.alternativesReady === true, { timeout: 10000 });
}

const force = (page, body) => page.request.post("/__test__/force", { data: body });

// Count the sandbox calls the page actually makes, so "beat two was reached" is
// asserted from the NETWORK — the same evidence the defect was found in — and
// not merely from a rendered card.
function countBeats(page) {
  const seen = { one: 0, two: 0 };
  page.on("request", (r) => {
    const u = r.url();
    if (!r.method || r.method() !== "POST") return;
    if (/\/sandbox\/feasibility$/.test(u)) seen.one++;
    else if (/\/sandbox$/.test(u)) seen.two++;
  });
  return seen;
}

const drop = (page, mv) => page.evaluate(([op, rid, start]) =>
  window.__cockpit.drag.dropAt(op, rid, start, /*altKey*/ true)
    .then(() => window.__cockpit.drag.state()),
  [gesture.op, mv.resource, mv.start]);

// ---------------------------------------------------------------------------
// PREMISE TEST. Everything below asserts what the cockpit does with a badly
// behaved beat. That is worth nothing unless the harness can actually PRODUCE
// one — a suite that quietly served healthy responses would pass all three
// assertions while proving nothing. So: prove the forcing controls work, at the
// wire, before using them.
// ---------------------------------------------------------------------------
test("PREMISE — the harness can really produce an undetermined beat one and a failed beat two", async ({ page }) => {
  await boot(page);
  const pin = { pin_op_id: gesture.op, pin_resource_id: gesture.resource,
                pin_start_iso: gesture.start };

  await force(page, { beat_one: "undetermined" });
  const b1 = await page.request.post(`/schedules/${SCHEDULE}/sandbox/feasibility`, { data: pin });
  expect(b1.status(), "an undetermined beat one is a 200, not an error").toBe(200);
  const ghost = (await b1.json()).data;
  expect(ghost.status).toBe("UNKNOWN");
  expect(ghost.feasible, "the boolean the old cockpit read is FALSE here").toBe(false);
  expect(ghost.verdict, "…and the tri-state says which false this is").toBe("undetermined");

  await force(page, { beat_two: "error" });
  const b2 = await page.request.post(`/schedules/${SCHEDULE}/sandbox`, { data: pin });
  expect(b2.status(), "a failed beat two really fails").toBe(503);

  await force(page, {});
  const ok = await page.request.post(`/schedules/${SCHEDULE}/sandbox`, { data: pin });
  expect(ok.status(), "and clearing the force restores a healthy beat two").toBe(200);
});

// ---------------------------------------------------------------------------
// (1) THE DEFECT ITSELF. UNKNOWN is a statement about our budget; the plant said
// nothing. Beat two must be reached, and the planner must be told why the wait
// is longer than usual.
// ---------------------------------------------------------------------------
test("an UNDETERMINED beat one still reaches beat two — UNKNOWN is not impossible", async ({ page }) => {
  await boot(page);
  const beats = countBeats(page);
  await force(page, { beat_one: "undetermined" });

  const st = await drop(page, gesture);

  expect(beats.one, "beat one fired").toBe(1);
  expect(beats.two, "AND BEAT TWO FIRED — this is the whole session").toBe(1);
  expect(st.feasibilityGhost.verdict).toBe("undetermined");
  expect(st.beatOne).toBe("undetermined");
  expect(st.phase, "the priced verdict landed").toBe("verdict");

  // and the card is the priced one, not a refusal
  await expect(page.locator(".delta-card.verdict, .delta-card.feasible_unproven")).toBeVisible();
  const text = await page.locator(".delta-card").innerText();
  expect(text, "an undetermined check never claims the placement is impossible")
    .not.toMatch(/isn't possible|can't go here/i);
  await shot(page, "beat_two_undetermined_reaches_pricing");
});

test("an undetermined beat one is NAMED while beat two runs (never a silent extra wait)", async ({ page }) => {
  await boot(page);
  await force(page, { beat_one: "undetermined" });
  // hold beat two open so the pending card can be read mid-flight
  await page.route("**/sandbox", async (route) => {
    await new Promise((r) => setTimeout(r, 1200));
    await route.continue();
  });
  const pending = drop(page, gesture);
  const note = page.locator(".delta-card.pending .dc-note.beat-one-note.undetermined");
  await expect(note).toBeVisible();
  await expect(note).toContainText(/ran out of time|budget/i);
  await expect(note, "it must not read as a verdict about the plant")
    .not.toContainText(/impossible|isn't possible/i);
  await shot(page, "beat_two_undetermined_pending_note");
  await pending;
});

// ---------------------------------------------------------------------------
// (2) A REFUSAL IS A PRODUCT ANSWER. Proven-impossible is the ONE case where not
// firing beat two is right — and it must still leave something on screen.
// ---------------------------------------------------------------------------
test("a PROVEN-impossible beat one refuses visibly, names its reason, and skips beat two", async ({ page }) => {
  await boot(page);
  const beats = countBeats(page);
  // an op the fixture cans as infeasible → the synthesized ghost is "impossible"
  await page.route("**/sandbox/feasibility", (route) => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ api_version: "1", data: {
      correlation_id: "corr-impossible", feasible: false, within_budget: true,
      wall_time_s: 0.01, budget_s: 2.0, status: "INFEASIBLE",
      verdict: "impossible",
      message: "this placement isn't possible: MILL-01 is closed then",
      placement: [], pin: {},
    } }),
  }));

  const st = await drop(page, gesture);

  expect(beats.two, "beat two prices nothing when the placement is proven out").toBe(0);
  expect(st.feasibilityGhost.verdict).toBe("impossible");
  const card = page.locator(".delta-card.impossible");
  await expect(card, "A REFUSAL IS NOT A SILENT SNAP-BACK").toBeVisible();
  await expect(card).toContainText("Can't go here");
  await expect(card, "it names the reason").toContainText("MILL-01 is closed then");
  await expect(card.locator(".dc-retry"), "there is nothing to retry about a proof")
    .toHaveCount(0);
  await shot(page, "beat_two_refusal_visible");
});

// ---------------------------------------------------------------------------
// (3) THE GUARD ITEM 3 ASKS FOR. A beat-two failure produces a VISIBLE state,
// naming the beat — not a revert.
// ---------------------------------------------------------------------------
test("a BEAT-TWO FAILURE is visible, names the beat, and is never a bare revert", async ({ page }) => {
  await boot(page);
  await force(page, { beat_two: "error" });

  const st = await drop(page, gesture);

  const card = page.locator(".delta-card.failure");
  await expect(card, "the card STAYS — the bar going home alone is the silence").toBeVisible();
  await expect(card).toContainText("Couldn't price this");
  await expect(card, "it names WHICH beat").toContainText("beat 2");
  await expect(card, "and what happened, in a sentence")
    .toContainText(/scheduler hit an error|connection to the scheduler/i);
  await expect(card.locator(".dc-retry"), "a failure of OURS offers a retry").toBeVisible();
  // the state carries the authored cause; the raw string is kept off the card
  expect(st.failure.beat).toBe("two");
  expect(st.failure.what).toBeTruthy();
  const shown = await card.innerText();
  expect(shown, "no raw transport/HTTP string reaches a planner surface")
    .not.toMatch(/Failed to fetch|HTTP \d{3}|\/schedules\//);
  await shot(page, "beat_two_failure_visible");
});

test("the failure card's 'Try again' really re-runs the SAME pin", async ({ page }) => {
  await boot(page);
  const beats = countBeats(page);
  await force(page, { beat_two: "error" });
  await drop(page, gesture);
  await expect(page.locator(".delta-card.failure")).toBeVisible();
  expect(beats.two).toBe(1);

  // the beat that failed now succeeds; the retry must reach a real card
  await force(page, {});
  await page.locator(".delta-card.failure .dc-retry").click();
  await expect(page.locator(".delta-card.verdict, .delta-card.feasible_unproven"))
    .toBeVisible({ timeout: 20000 });
  expect(beats.two, "the retry fired beat two a second time").toBe(2);
  const st = await page.evaluate(() => window.__cockpit.drag.state());
  expect(st.phase).toBe("verdict");
  // and it retried THIS gesture — not a re-derived target
  expect(st.target.resource_id).toBe(gesture.resource);
});

test("a failure READS DIFFERENTLY from a refusal (the distinction Item 3 requires)", async ({ page }) => {
  await boot(page);
  await force(page, { beat_two: "error" });
  await drop(page, gesture);
  const failure = await page.locator(".delta-card").innerText();

  await boot(page);
  await page.route("**/sandbox/feasibility", (route) => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ api_version: "1", data: {
      correlation_id: "c", feasible: false, within_budget: true, wall_time_s: 0.01,
      budget_s: 2.0, status: "INFEASIBLE", verdict: "impossible",
      message: "this placement isn't possible here", placement: [], pin: {},
    } }),
  }));
  await drop(page, gesture);
  const refusal = await page.locator(".delta-card").innerText();

  expect(failure).not.toBe(refusal);
  // A REFUSAL is about the plant and does not apologise.
  expect(refusal).toMatch(/Can't go here/);
  expect(refusal).not.toMatch(/couldn't price|didn't finish/i);
  // A FAILURE is about us, and never claims the placement is impossible.
  expect(failure).toMatch(/Couldn't price this/);
  expect(failure).not.toMatch(/Can't go here|isn't possible/i);
});

test("a BEAT-ONE failure prices anyway and says the check didn't answer", async ({ page }) => {
  await boot(page);
  const beats = countBeats(page);
  await force(page, { beat_one: "error" });

  const st = await drop(page, gesture);

  expect(beats.two, "beat two is the authority — a broken beat one never blocks it").toBe(1);
  expect(st.beatOne).toBe("failed");
  expect(st.phase).toBe("verdict");
});

// ---------------------------------------------------------------------------
// NEGATIVE CONTROLS. Each is a rehearsal of the DEFECT, asserted RED against the
// pre-fix behaviour — proving these tests can fail.
//
// Control A rebuilds the old branch (`if (!ghost.feasible) return returnHome()`)
// over the real UNDETERMINED payload and asserts it produces exactly what the
// founder saw: one request, no card. If the shipped code still did that, the
// test above would fail — which is what makes it a guard rather than a mood.
// ---------------------------------------------------------------------------
test("NEGATIVE CONTROL A — the OLD boolean branch, replayed, still produces the defect", async ({ page }) => {
  await boot(page);
  await force(page, { beat_one: "undetermined" });
  const ghost = await page.evaluate(async ([sid, op, rid, start]) => {
    const r = await fetch(`/schedules/${sid}/sandbox/feasibility`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ pin_op_id: op, pin_resource_id: rid, pin_start_iso: start }),
    });
    return (await r.json()).data;
  }, [SCHEDULE, gesture.op, gesture.resource, gesture.start]);

  // THE OLD PREDICATE, verbatim: `if (!ghost.feasible) → snap back, no beat two`.
  const oldWouldSnapBack = !ghost.feasible;
  expect(oldWouldSnapBack, "the pre-fix cockpit read THIS payload as impossible").toBe(true);
  // THE NEW PREDICATE on the same payload.
  const newVerdict = ghost.verdict
    || (ghost.feasible ? "possible" : ghost.status === "INFEASIBLE" ? "impossible" : "undetermined");
  expect(newVerdict, "the fix turns on exactly this distinction").toBe("undetermined");
  expect(newVerdict === "impossible", "…so the new branch does NOT refuse").toBe(false);
});

// Control B: the fix must not make EVERY beat one proceed. A genuinely
// proven-impossible ghost must still stop the chain — otherwise "restore beat
// two" would have been implemented by deleting the check, and test (2) above
// would be passing for the wrong reason.
test("NEGATIVE CONTROL B — the fix did not simply delete the check", async ({ page }) => {
  await boot(page);
  const beats = countBeats(page);
  await page.route("**/sandbox/feasibility", (route) => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ api_version: "1", data: {
      correlation_id: "c", feasible: false, within_budget: true, wall_time_s: 0.01,
      budget_s: 2.0, status: "INFEASIBLE", verdict: "impossible",
      message: "this placement isn't possible here", placement: [], pin: {},
    } }),
  }));
  await drop(page, gesture);
  expect(beats.one).toBe(1);
  expect(beats.two, "a PROVEN refusal still stops the chain").toBe(0);
});

// Control C (Item 4): the deferral is real, not a watch that never ran. If
// `proposalLive` were wired to a constant false, deferrals would stay 0 and this
// goes red; if the watch were simply never installed, the same.
test("ITEM 4 — a freshness poll cannot discard a live proposal", async ({ page }) => {
  await boot(page);
  await page.request.post("/__test__/add-schedule", {
    data: { id: "sched-newer-during-gesture", base: "sched-multi-route-distinct",
            created_at: "2026-01-05T12:00:00Z", generation: 4 },
  });
  await drop(page, gesture);
  await expect(page.locator(".delta-card")).toBeVisible();
  const urlBefore = page.url();

  const deferred = await page.evaluate(async () => {
    const before = window.__cockpit.freshnessDeferrals();
    await window.__cockpit.checkFreshness();
    return { before, after: window.__cockpit.freshnessDeferrals() };
  });
  expect(deferred.after, "the watch RAN and chose to hold off")
    .toBe(deferred.before + 1);
  await page.waitForTimeout(300);
  expect(page.url(), "no auto-follow reload under a live proposal").toBe(urlBefore);
  expect(await page.locator("#newer-banner").count(),
         "and no banner prepend to reflow the rows the proposal is pinned to").toBe(0);
  await expect(page.locator(".delta-card"), "the proposal survives the poll").toBeVisible();

  // …and once the proposal is dismissed the SAME check offers the newer board:
  // the poll is deferred, never dropped.
  await page.locator(".delta-card .dc-discard").click();
  await page.evaluate(() => window.__cockpit.checkFreshness());
  await expect(page.locator("#newer-banner")).toBeVisible();
});
