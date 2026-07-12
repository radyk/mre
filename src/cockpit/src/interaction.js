// Tier-0 interaction-payload delivery (CU1, docs/04 R-T1d).
//
// The board renders READ-ONLY immediately from the main document; this module
// fetches the Tier-0 legality payload (GET /schedules/{id}/interaction) in the
// BACKGROUND after first paint — never inside the render path, never at grab
// time (a network round-trip must not sit inside Tier-0's latency budget).
// When it arrives, drag affordances enable (a stub flag for interim-A; the
// gesture surface itself is 3.2b).
//
// Stale-while-revalidate: the payload is cached per schedule VERSION (the
// schedule id — a new solve mints a new id, superseding the old). A repeated
// load of the same id serves the cached payload immediately AND revalidates in
// the background, so a schedule-version change is picked up without ever
// blocking on the network.
import { getScheduleInteraction } from "./api.js";

const _cache = new Map();   // scheduleId -> interaction envelope data

// Kick off the background fetch for `id`. `onReady(payload)` fires when a
// payload is available (from cache first if present, then again after a
// successful revalidation if it changed). Returns the in-flight promise.
export function loadInteraction(id, onReady) {
  const cached = _cache.get(id);
  if (cached) onReady(cached, { fromCache: true });   // serve stale immediately
  const revalidate = getScheduleInteraction(id).then((data) => {
    if (!data) return cached || null;   // 404/absent: stay green-only
    const changed = !cached || JSON.stringify(data) !== JSON.stringify(cached);
    _cache.set(id, data);
    if (changed) onReady(data, { fromCache: false });
    return data;
  });
  return revalidate;
}

// Bind the payload lifecycle to the board + the harness/demo hook. The board
// gets the payload (the Tier-0 legality library will consume it in 3.2b) and a
// stub drag-enabled flag; window.__cockpit exposes both for the tests.
export function wireInteraction(id, board, hook) {
  hook.interactionReady = false;
  hook.dragEnabled = false;         // stub: the gesture surface is 3.2b
  hook.interaction = null;
  const onReady = (payload) => {
    hook.interaction = payload.interaction || null;
    hook.interactionReady = true;
    hook.dragEnabled = true;
    if (board?.setInteraction) board.setInteraction(payload.interaction || null);
    // a DOM signal the screenshot harness (and any external probe) can await
    board?.host?.setAttribute?.("data-drag-enabled", "true");
  };
  return loadInteraction(id, onReady);
}
