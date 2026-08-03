// R-GP1 — THE PLACEMENT DIGEST, AND WHAT "CURRENT" MEANS (Session 4B.34 Item 6).
//
// PURE, framework-free (unit-tested in the `logic` harness project).
//
// THE SPECIMEN. `rolling-b4dd3010751f` is a re-freeze ceremony child of the
// Khalil demo board: 4B.28 minted it by thawing eight committed operations and
// freezing them back, and PROVED at the time that every placement was
// unchanged — a thaw changes AUTHORITY, never position. It is nonetheless a
// newer registry row, so the picker showed it as CURRENT above the board it is a
// copy of, and the freshness watch offered to move the planner onto it. The
// demo board was outranked by an artifact of a ceremony performed ON it.
//
// THE RULE. CURRENT means "the most recent PLACEMENT-BEARING state of this
// lineage". A child whose placements are identical to its parent's is shown in
// the lineage, never outranks its parent as CURRENT, and never fires the
// "newer schedule" banner. The banner interrupts a planner for a DIFFERENT PLAN
// and for nothing else.
//
// WHY A DIGEST AND NOT THE LEDGER. Measured on this very lineage: the Khalil
// board, both ceremony children AND a zero-move accepted edit all carry ledger
// $1,667,467.80 — and so does `e2e18e8c`, which HAS moved an operation. Four
// identical plans and one different one, all wearing the same number. The ledger
// cannot tell them apart; only the placements can.
//
// WHAT IS PLACEMENT-BEARING. The operation, the machine it is on, and when it
// runs — nothing else. Deliberately EXCLUDED:
//   * `assignment_id`, which a rebind rewrites while the plan stands still;
//   * commitment state and standing pins, which is exactly what an authority-only
//     ceremony changes and would therefore defeat the whole comparison;
//   * cost, lateness and every derived figure, which are consequences of the
//     placements and not the placements.
//
// NO SCHEMA OR CONTRACT CHANGE. The key is DERIVED LIVE from the document each
// client already fetches. A durable home for it would be a registry column and a
// contract bump; per the brief this derives instead, and says so here.

// The canonical, order-stable placement key. EQUALITY IS TESTED ON THIS STRING,
// never on the short digest below — a hash comparison would let a collision
// report two different plans as the same plan, and "these boards are identical"
// is precisely the claim that must not be manufactured.
export function placementKey(doc) {
  const d = (doc && doc.document) || doc;
  if (!d || !Array.isArray(d.assignments)) return null;
  const rows = d.assignments.map((a) => {
    const chunks = (a.chunks || [])
      .map((c) => `${c.start}~${c.end}`)
      .sort()
      .join(",");
    return `${a.operation_ref}|${a.resource_id}|${chunks}`;
  });
  rows.sort();
  return `${rows.length}#${rows.join("\n")}`;
}

// A SHORT HANDLE FOR THE KEY — for display and for a probe to assert on. FNV-1a,
// two lanes, hex. It is a label, not evidence: nothing decides anything by
// comparing these.
export function shortDigest(key) {
  if (key == null) return null;
  let h1 = 0x811c9dc5, h2 = 0x01000193;
  for (let i = 0; i < key.length; i++) {
    const c = key.charCodeAt(i);
    h1 ^= c; h1 = Math.imul(h1, 0x01000193) >>> 0;
    h2 = Math.imul(h2 ^ c, 0x85ebca6b) >>> 0;
  }
  return (h1.toString(16).padStart(8, "0") + h2.toString(16).padStart(8, "0")).slice(0, 12);
}

// HOW A CHILD WAS MINTED, read from the structural naming the minting code
// itself writes — the same class of derivation as `scheduleKind`, and for the
// same reason: the registry carries no column for it and inventing one is a
// schema change.
//   * an accepted planner edit gets a FRESH snapshot, `snap-edit-<...>`;
//   * a boundary ceremony SHARES ITS PARENT'S run and snapshot (4B.28) — the
//     placements ARE the parent's placements, which is why it can.
export function childOrigin(meta) {
  if (!meta || !meta.parent_schedule_id) return "root";
  return /^snap-edit-/i.test(String(meta.snapshot_id || "")) ? "edit" : "ceremony";
}

export const BADGE = {
  CHANGED: "placements-changed",
  AUTHORITY: "authority-only",
  EDIT: "accepted-edit",
  UNKNOWN: null,
};

// The badge for one row. `parentKey`/`childKey` are placement keys; either being
// null means NOT YET KNOWN, and an unknown comparison yields no badge rather
// than a guess — a row that says nothing is honest, a row that says
// "authority-only" because a fetch failed is not.
//
// PRECEDENCE IS PLACEMENTS FIRST. A child that moved work is PLACEMENTS-CHANGED
// however it was minted. Only among placement-IDENTICAL children does it matter
// whether a planner accepted something (ACCEPTED-EDIT — a real decision was
// recorded, against the same plan) or a ceremony ran (AUTHORITY-ONLY).
export function badgeFor({ parentKey, childKey, origin }) {
  if (origin === "root") return BADGE.UNKNOWN;
  if (parentKey == null || childKey == null) return BADGE.UNKNOWN;
  if (parentKey !== childKey) return BADGE.CHANGED;
  return origin === "edit" ? BADGE.EDIT : BADGE.AUTHORITY;
}

// Does this badge represent a different PLAN? The one question CURRENT and the
// banner are allowed to ask.
//
// A ZERO-MOVE ACCEPTED EDIT ANSWERS NO, AND THAT IS A JUDGEMENT WORTH NAMING.
// 4B.32 measured accepts whose ledger and placements were both unchanged;
// `caff8efa` is one, and its placement key is its parent's to the character. A
// decision was genuinely recorded — so it earns its own badge and appears in the
// lineage — but the plan a planner is looking at did not change, and R-GP1's
// rule is about the plan. Interrupting someone to move them onto an identical
// board is the behaviour this ruling exists to stop, whatever minted it.
export function isPlanChange(badge) { return badge === BADGE.CHANGED; }

// The listing row, decorated. `keys` maps schedule id → placement key (or
// undefined where not yet fetched); `metas` maps id → its /meta. Pure: it reads
// two maps and returns a description, so a guard can build the maps by hand.
export function describeRow(row, { keys = {}, metas = {} } = {}) {
  const meta = metas[row.id] || null;
  const origin = childOrigin(meta);
  const parentId = meta && meta.parent_schedule_id;
  const childKey = keys[row.id] ?? null;
  const parentKey = parentId ? (keys[parentId] ?? null) : null;
  const badge = badgeFor({ parentKey, childKey, origin });
  return {
    id: row.id,
    parentId: parentId || null,
    origin,
    badge,
    planChange: isPlanChange(badge),
    digest: shortDigest(childKey),
  };
}

// WHICH ROW IS CURRENT. Not "the newest row" — the newest row whose placements
// are not merely inherited. A child that changed nothing about the plan defers
// to the ancestor it copied, so the demo board keeps its own crown.
//
// Walks the parent chain: a row is placement-bearing unless it is a
// placement-identical child, in which case its parent stands in its place. Rows
// whose comparison is unknown are treated as placement-bearing (fail open —
// never hide a board we cannot prove is a copy).
export function resolveCurrent(rows, { keys = {}, metas = {} } = {}) {
  if (!Array.isArray(rows) || !rows.length) return null;
  const byId = new Map(rows.map((r) => [r.id, r]));
  const rank = (r) => (r.created_at ? Date.parse(r.created_at) : 0);
  const bearer = (id, seen = new Set()) => {
    if (!id || seen.has(id) || !byId.has(id)) return id || null;
    seen.add(id);
    const d = describeRow(byId.get(id), { keys, metas });
    if (d.parentId && byId.has(d.parentId)
        && (d.badge === BADGE.AUTHORITY || d.badge === BADGE.EDIT)) {
      return bearer(d.parentId, seen);
    }
    return id;
  };
  let best = null, bestKey = -Infinity;
  for (const r of rows) {
    if (!r || !r.id || r.status === "superseded" || r.is_scenario) continue;
    const b = bearer(r.id);
    const row = byId.get(b);
    if (!row) continue;
    const k = rank(row);
    if (k >= bestKey) { best = b; bestKey = k; }
  }
  return best;
}
