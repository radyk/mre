// R-GP1's fetching half (Session 4B.34 Item 6). `lineage.js` is the pure rule;
// this is the only place that goes to the network for it.
//
// DERIVED LIVE, CACHED PER TAB. A schedule's placements do not change — a new
// plan is a NEW schedule id — so a key, once read, is good for the life of the
// page and every caller shares one copy. That is what makes a comparison the
// registry has no column for affordable enough to run on a background poll.
//
// The `null` returned on failure means NOT KNOWN, never "no placements": every
// caller treats an unknown as un-comparable and falls back to the pre-R-GP1
// behaviour, which is to offer the newer row.

import { getSchedule, getScheduleMeta } from "./api.js";
import { placementKey, shortDigest, describeRow, resolveCurrent } from "./lineage.js";

const keys = new Map();      // id → placement key | null
const metas = new Map();     // id → /meta | null
const docs = new Map();      // id → the fetched document (facts for the picker)
const inflight = new Map();

async function once(map, id, fetcher) {
  if (map.has(id)) return map.get(id);
  const tag = `${map === keys ? "k" : "m"}:${id}`;
  if (!inflight.has(tag)) inflight.set(tag, fetcher().catch(() => null));
  const v = await inflight.get(tag);
  inflight.delete(tag);
  map.set(id, v);
  return v;
}

// The placement key for one schedule, fetching its document once.
export async function placementKeyFor(id) {
  if (!id) return null;
  if (keys.has(id)) return keys.get(id);
  const v = await once(keys, id, async () => {
    const data = await getSchedule(id);
    const doc = (data && data.document) || data;
    if (doc) docs.set(id, doc);
    return placementKey(doc);
  });
  return v;
}

export async function metaFor(id) {
  if (!id) return null;
  return once(metas, id, () => getScheduleMeta(id));
}

// IS `candidateId` A DESCENDANT OF `ancestorId`? R-GP1's suppression is scoped
// to a LINEAGE — the ruling compares parent↔child — and this is what enforces it.
//
// THE SCOPE IS LOad-BEARING, not tidiness. Without it the rule reads "any newer
// schedule with identical placements is not a newer plan", which silently
// swallows the RESUBMIT case: a planner fixes data in Excel and re-solves,
// minting a schedule under a NEW submission that happens to place work
// identically. That is a different plan of record and the tab must still follow
// it. Caught by `deeplink.spec.mjs`'s auto-follow guard, which went red the
// moment the comparison was left unscoped.
export async function isDescendantOf(candidateId, ancestorId) {
  if (!candidateId || !ancestorId) return false;
  let cur = candidateId;
  const seen = new Set();
  for (let hops = 0; hops < 32; hops++) {
    if (seen.has(cur)) return false;            // a cycle is not a lineage
    seen.add(cur);
    const meta = await metaFor(cur);
    const parent = meta && meta.parent_schedule_id;
    if (!parent) return false;
    if (parent === ancestorId) return true;
    cur = parent;
  }
  return false;
}

// The derived facts a picker row states. EVERY ONE IS READ, NEVER NAMED IN A
// SCHEMA: the ledger and the bar count come off the document, the calibration
// marker off `solver.calibration` (R-CAL1 puts it there even when the answer is
// "nobody has measured this plant", which is why its ABSENCE is also a fact).
export async function rowFactsFor(id) {
  if (!id) return null;
  await placementKeyFor(id);
  const meta = await metaFor(id);
  const doc = docs.get(id) || null;
  const cost = (doc && doc.cost_summary) || null;
  const solver = (doc && doc.solver) || null;
  return {
    id,
    key: keys.get(id) ?? null,
    digest: shortDigest(keys.get(id) ?? null),
    bars: doc && Array.isArray(doc.assignments) ? doc.assignments.length : null,
    ledger: cost && cost.total != null ? cost.total : null,
    calibrated: solver ? !!solver.calibration : null,
    parentId: (meta && meta.parent_schedule_id) || null,
    createdAt: (meta && meta.created_at) || null,
    meta,
  };
}

// Decorate a whole listing. Rows resolve PROGRESSIVELY — `onRow` fires as each
// lands — because a picker that blocked on twenty 400 KB documents before
// drawing anything would have traded one annoyance for a worse one.
export async function decorate(rows, onRow, onDone) {
  const ids = rows.map((r) => r && r.id).filter(Boolean);
  for (const id of ids) {
    /* eslint-disable no-await-in-loop */
    const facts = await rowFactsFor(id);
    const meta = metas.get(id) || null;
    if (meta && meta.parent_schedule_id) await placementKeyFor(meta.parent_schedule_id);
    const desc = describeRow({ id }, { keys: asObj(keys), metas: asObj(metas) });
    if (onRow) onRow(id, { ...facts, ...desc });
  }
  // R-GP1's CURRENT: the most recent PLACEMENT-BEARING row, computed once every
  // key is in. Announced only at the end — a partial answer would name a
  // different row than the complete one and correct itself on screen.
  if (onDone) onDone(resolveCurrent(rows, { keys: asObj(keys), metas: asObj(metas) }));
}

const asObj = (m) => Object.fromEntries(m.entries());
export const snapshot = () => ({ keys: asObj(keys), metas: asObj(metas) });

// harness seam: seed the caches so a guard can drive the RULE without a server.
export function _seed({ keys: k = {}, metas: m = {}, docs: d = {} } = {}) {
  for (const [id, v] of Object.entries(k)) keys.set(id, v);
  for (const [id, v] of Object.entries(m)) metas.set(id, v);
  for (const [id, v] of Object.entries(d)) docs.set(id, v);
}
export function _reset() { keys.clear(); metas.clear(); docs.clear(); inflight.clear(); }
