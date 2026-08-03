// R-GP1 — the placement digest and what CURRENT means (Session 4B.34 Item 6).
// Pure logic: no rendering, runs once in the `logic` project alongside
// legality / rowstats / freshness / schedulepicker.
//
// THE SPECIMEN IT IS BUILT FROM is real and is named in lineage.js: a re-freeze
// ceremony child of the Khalil demo board, placement-identical to it, sitting
// above it as CURRENT and firing the "newer schedule" banner over it.
import { test, expect } from "@playwright/test";
import {
  placementKey, shortDigest, childOrigin, badgeFor, isPlanChange,
  describeRow, resolveCurrent, BADGE,
} from "../../src/cockpit/src/lineage.js";
import { findNewerSchedule } from "../../src/cockpit/src/freshness.js";

// A minimal document: three placed operations. `chunks` is what carries time.
const docOf = (rows) => ({
  assignments: rows.map(([op, res, start, end], i) => ({
    assignment_id: `a${i}`,                 // deliberately NOT in the key
    operation_ref: op, resource_id: res,
    chunks: [{ chunk_seq: 1, start, end }],
  })),
});
const PARENT = docOf([
  ["op-1", "CUT-01", "2026-01-05T07:00:00Z", "2026-01-05T09:00:00Z"],
  ["op-2", "MILL-01", "2026-01-05T09:00:00Z", "2026-01-05T11:00:00Z"],
  ["op-3", "FIN-01", "2026-01-06T07:00:00Z", "2026-01-06T08:00:00Z"],
]);

// ---------------------------------------------------------------- the key ---

test("PREMISE — an authority-only child really is placement-identical", () => {
  // A thaw changes commitment state and standing pins and moves NOTHING. The
  // fixture child below carries different authority fields and the same
  // placements; if this premise failed, every banner assertion in this file
  // would be proving nothing.
  const authorityOnly = {
    assignments: PARENT.assignments.map((a) => ({
      ...a,
      assignment_id: `rebound-${a.assignment_id}`,   // a rebind rewrites these
      commitment_state: "active_window",             // was committed
      standing_pin: true,                            // the thaw's pin
    })),
  };
  expect(placementKey(authorityOnly), "same plan, different authority")
    .toBe(placementKey(PARENT));
  // …and the premise's own negative: a moved operation MUST change the key, or
  // "identical" would be trivially true of everything.
  const moved = docOf([
    ["op-1", "CUT-01", "2026-01-05T07:00:00Z", "2026-01-05T09:00:00Z"],
    ["op-2", "MILL-01", "2026-01-06T09:00:00Z", "2026-01-06T11:00:00Z"],  // +1 day
    ["op-3", "FIN-01", "2026-01-06T07:00:00Z", "2026-01-06T08:00:00Z"],
  ]);
  expect(placementKey(moved)).not.toBe(placementKey(PARENT));
});

test("the key is order-stable — the same plan listed in any order is one key", () => {
  const shuffled = { assignments: [...PARENT.assignments].reverse() };
  expect(placementKey(shuffled)).toBe(placementKey(PARENT));
});

test("a MACHINE change is a placement change", () => {
  const rehoused = docOf([
    ["op-1", "CUT-02", "2026-01-05T07:00:00Z", "2026-01-05T09:00:00Z"],  // CUT-01→02
    ["op-2", "MILL-01", "2026-01-05T09:00:00Z", "2026-01-05T11:00:00Z"],
    ["op-3", "FIN-01", "2026-01-06T07:00:00Z", "2026-01-06T08:00:00Z"],
  ]);
  expect(placementKey(rehoused)).not.toBe(placementKey(PARENT));
});

test("a document with no assignments has NO key — not an empty one", () => {
  // null means "not known", and every caller falls back to pre-R-GP1 behaviour
  // on it. An empty-string key would compare EQUAL to another unreadable
  // document and silently suppress a real banner.
  expect(placementKey(null)).toBeNull();
  expect(placementKey({})).toBeNull();
  expect(shortDigest(null)).toBeNull();
});

test("the short digest is a label, and equality is never decided on it", () => {
  expect(shortDigest(placementKey(PARENT))).toHaveLength(12);
  expect(shortDigest(placementKey(PARENT)))
    .toBe(shortDigest(placementKey({ assignments: [...PARENT.assignments].reverse() })));
});

// ------------------------------------------------------------- the badges ---

test("origin is read from the snapshot naming the minting code writes", () => {
  expect(childOrigin({ parent_schedule_id: "p", snapshot_id: "snap-edit-077d6cbb" })).toBe("edit");
  expect(childOrigin({ parent_schedule_id: "p", snapshot_id: "snap-rolling" })).toBe("ceremony");
  expect(childOrigin({ snapshot_id: "snap-rolling" })).toBe("root");   // no parent
  expect(childOrigin(null)).toBe("root");
});

test("badges: placements decide first, origin only separates the identical", () => {
  const k = placementKey(PARENT), other = placementKey(docOf([["op-9", "X", "a", "b"]]));
  // a child that moved work is PLACEMENTS-CHANGED however it was minted
  expect(badgeFor({ parentKey: k, childKey: other, origin: "edit" })).toBe(BADGE.CHANGED);
  expect(badgeFor({ parentKey: k, childKey: other, origin: "ceremony" })).toBe(BADGE.CHANGED);
  // among placement-identical children, HOW it was minted is the distinction
  expect(badgeFor({ parentKey: k, childKey: k, origin: "ceremony" })).toBe(BADGE.AUTHORITY);
  expect(badgeFor({ parentKey: k, childKey: k, origin: "edit" })).toBe(BADGE.EDIT);
  // a root has no parent to differ from
  expect(badgeFor({ parentKey: null, childKey: k, origin: "root" })).toBeNull();
});

test("an UNKNOWN comparison yields no badge — never a guess", () => {
  const k = placementKey(PARENT);
  expect(badgeFor({ parentKey: null, childKey: k, origin: "ceremony" })).toBeNull();
  expect(badgeFor({ parentKey: k, childKey: null, origin: "edit" })).toBeNull();
});

test("only PLACEMENTS-CHANGED is a plan change — a zero-move accept is not", () => {
  expect(isPlanChange(BADGE.CHANGED)).toBe(true);
  expect(isPlanChange(BADGE.AUTHORITY)).toBe(false);
  // 4B.32 measured accepts whose placements and ledger were both unchanged;
  // `caff8efa` on the live board is one. A decision WAS recorded — hence its own
  // badge — but the plan did not change, and the banner is about the plan.
  expect(isPlanChange(BADGE.EDIT)).toBe(false);
  expect(isPlanChange(null)).toBe(false);
});

// ------------------------------------------------------------- the ruling ---

const K = placementKey(PARENT);
const OTHER = placementKey(docOf([["op-1", "CUT-01", "2026-02-01T07:00:00Z", "2026-02-01T09:00:00Z"]]));
const ROWS = [
  { id: "board", created_at: "2026-08-02T02:16:00Z", status: "proposed" },
  { id: "thaw", created_at: "2026-08-02T03:06:00Z", status: "proposed" },
  { id: "refreeze", created_at: "2026-08-02T03:07:00Z", status: "proposed" },
];
const KEYS = { board: K, thaw: K, refreeze: K };
const METAS = {
  board: { snapshot_id: "snap-rolling" },
  thaw: { parent_schedule_id: "board", snapshot_id: "snap-rolling" },
  refreeze: { parent_schedule_id: "thaw", snapshot_id: "snap-rolling" },
};

test("CURRENT is the board, not the ceremony children stacked on top of it", () => {
  // THE WHOLE DEFECT IN ONE ASSERTION: `refreeze` is the newest row by a minute
  // and is a byte-copy of `board`'s plan.
  expect(resolveCurrent(ROWS, { keys: KEYS, metas: METAS })).toBe("board");
});

test("a child that MOVED work does become CURRENT", () => {
  const rows = [...ROWS, { id: "edit", created_at: "2026-08-02T21:29:00Z", status: "proposed" }];
  const keys = { ...KEYS, edit: OTHER };
  const metas = { ...METAS, edit: { parent_schedule_id: "refreeze", snapshot_id: "snap-edit-abc" } };
  expect(resolveCurrent(rows, { keys, metas })).toBe("edit");
});

test("a chain of ceremonies still resolves to the plan at its root", () => {
  const d = describeRow(ROWS[2], { keys: KEYS, metas: METAS });
  expect(d.badge).toBe(BADGE.AUTHORITY);
  expect(d.parentId).toBe("thaw");
  expect(d.planChange).toBe(false);
});

test("an UNPROVEN copy is treated as placement-bearing (fails OPEN)", () => {
  // the refreeze document could not be read → it is not a proven copy, so it
  // keeps its newest-row standing rather than being hidden on a guess.
  const keys = { board: K, thaw: K };            // refreeze absent
  expect(resolveCurrent(ROWS, { keys, metas: METAS })).toBe("refreeze");
});

test("the BANNER does not fire for an authority-only newer row, and DOES for a real one",
  () => {
    const isCopy = (id) => KEYS[id] === KEYS.board;
    // pre-R-GP1: the newest row wins, whatever it contains.
    expect(findNewerSchedule("board", ROWS)).toBe("refreeze");
    // with the ruling in force: nothing newer is a different plan.
    expect(findNewerSchedule("board", ROWS, isCopy)).toBeNull();
    // and a genuinely different plan is still offered.
    const rows = [...ROWS, { id: "edit", created_at: "2026-08-02T21:29:00Z", status: "proposed" }];
    expect(findNewerSchedule("board", rows, (id) => id !== "edit" && isCopy(id))).toBe("edit");
  });

test("no predicate, or one that cannot answer, behaves exactly as before", () => {
  expect(findNewerSchedule("board", ROWS, null)).toBe("refreeze");
  expect(findNewerSchedule("board", ROWS, () => null)).toBe("refreeze");
  expect(findNewerSchedule("board", ROWS, () => undefined)).toBe("refreeze");
});
