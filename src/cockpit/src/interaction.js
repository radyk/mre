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
import {
  getScheduleInteraction, getScheduleAlternatives, postSandbox,
  priceOpAlternatives, getAlternativeMember, postAccept, postPublish,
  getSchedule,
} from "./api.js";
import { createGeometry } from "./drag/geometry.js";
import { createGestureController } from "./drag/controller.js";
import { mountTuningPanel } from "./drag/tuning.js";

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

// Bind the payload lifecycle to the board + the harness/demo hook. When the
// Tier-0 payload arrives (after first paint, R-T1d), stand up the 3.2b gesture
// controller against it — grab/shade/ghosts/magnets/drop/verdict/traces — and
// fetch the Tier-1 ghost payload (/alternatives) in the background to feed it.
// The dev build additionally mounts the feel tuning panel (CU6). Read-only
// until this resolves; drag affordances enable on arrival.
export function wireInteraction(id, board, hook, opts = {}) {
  const { doc, devMode = false, onVersionChange, onSuperseded } = opts;
  hook.interactionReady = false;
  hook.dragEnabled = false;
  hook.interaction = null;
  hook.drag = null;

  // The gesture controller's server surface: the sandbox re-solve (CU4, 3.2b),
  // plus the on-demand pricing + re-fetch + member-document lazy-load the
  // coverage + full-consequences work needs (session 3.3 CU1/CU4).
  const api = {
    postSandbox,
    priceOpAlternatives,
    getAlternativeMember,
    getAlternatives: getScheduleAlternatives,
    // accept/publish (CU1) + the rebind reads the controller needs after an edit
    postAccept,
    postPublish,
    getSchedule,
    getInteraction: getScheduleInteraction,
  };

  const onReady = (payload) => {
    const interaction = payload.interaction || null;
    hook.interaction = interaction;
    hook.interactionReady = true;
    if (board?.setInteraction) board.setInteraction(interaction);
    board?.host?.setAttribute?.("data-drag-enabled", "true");

    // Build the gesture controller once (idempotent: rebuild on a genuine
    // payload change under stale-while-revalidate is fine — a new solve = a new
    // id = a fresh boot, so in practice this runs once per cockpit load).
    if (!interaction || !doc || hook.drag) { hook.dragEnabled = !!hook.drag; return; }
    try {
      const geometry = createGeometry(board.timeline);
      const controller = createGestureController(board, geometry, {
        doc, interaction, api, scheduleId: id,
        onVersionChange: (newId, status) => {
          hook.scheduleId = newId;    // subsequent asks target the live version
          hook.versionChanged = { id: newId, status };   // synchronous, race-free
          if (onVersionChange) onVersionChange(newId, status);
        },
        // A live drop/accept that 409s "superseded" means a stale reference
        // slipped through — jump to the live successor (session 3.8 CU3).
        onSuperseded,
      });
      hook.drag = controller;
      hook.dragEnabled = true;
      if (devMode) mountTuningPanel(board.host.parentElement || board.host, controller);
      // ghosts arrive on their own endpoint, in the background (R-T1a) — a 404
      // (none built) leaves the surface Tier-0-green-only.
      getScheduleAlternatives(id).then((alt) => {
        if (alt) controller.setAlternatives(alt, null);
        hook.alternativesReady = true;
      });
    } catch (e) {
      hook.dragError = String(e?.message || e);
    }
  };
  return loadInteraction(id, onReady);
}
