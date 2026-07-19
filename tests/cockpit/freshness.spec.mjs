// Pure-logic regression for schedule-freshness detection (Session 4.3 CU6,
// rescoped Session 4.4 CU1). No rendering — runs once, theme-free, in the `logic`
// project (like legality / rowstats). Pins findNewerSchedule to the 4.4 scope:
// the newest LIVE schedule strictly newer than the bound one across the whole
// DATA ROOT (NOT the same submission — the resubmit blind spot that caused the
// sixth stale-tab incident), never a superseded one, never a same-instant tie.
import { test, expect } from "@playwright/test";
import { findNewerSchedule } from "../../src/cockpit/src/freshness.js";

// listing rows ordered oldest→newest (created_at asc), scenarios excluded.
const s = (id, created_at, status = "proposed", submission_id = "sub-1") =>
  ({ id, created_at, status, submission_id });

test("returns the newest live schedule strictly newer than the bound one", () => {
  const list = [
    s("a", "2026-01-05T09:00:00Z"),
    s("b", "2026-01-05T10:00:00Z"),
    s("c", "2026-01-05T11:00:00Z"),
  ];
  expect(findNewerSchedule("a", list)).toBe("c");
  expect(findNewerSchedule("b", list)).toBe("c");
  expect(findNewerSchedule("c", list)).toBeNull();   // already newest
});

test("CROSSES submission scope — a resubmit under a NEW submission IS offered (4.4 CU1)", () => {
  // the exact blind spot: the old rule required the same submission, so a
  // resubmit (a new submission id) was never noticed. Now it is.
  const list = [
    s("a", "2026-01-05T09:00:00Z", "proposed", "sub-orig"),
    s("resubmit", "2026-01-05T10:00:00Z", "proposed", "sub-fixed"),
  ];
  expect(findNewerSchedule("a", list)).toBe("resubmit");
});

test("a same-instant tie is NOT newer (unrelated live boards never cross-follow)", () => {
  const list = [
    s("a", "2026-01-05T09:41:00Z", "proposed", "sub-x"),
    s("b", "2026-01-05T09:41:00Z", "proposed", "sub-y"),
  ];
  expect(findNewerSchedule("a", list)).toBeNull();
  expect(findNewerSchedule("b", list)).toBeNull();
});

test("skips a superseded successor (never routes to a dead version)", () => {
  const list = [
    s("a", "2026-01-05T09:00:00Z"),
    s("b", "2026-01-05T10:00:00Z", "superseded"),
  ];
  expect(findNewerSchedule("a", list)).toBeNull();
  const list2 = [...list, s("c", "2026-01-05T11:00:00Z")];
  expect(findNewerSchedule("a", list2)).toBe("c");
});

test("scenarios are never offered even if they leak into the listing", () => {
  const list = [
    s("a", "2026-01-05T09:00:00Z"),
    { id: "whatif", created_at: "2026-01-05T10:00:00Z", status: "proposed", is_scenario: 1 },
  ];
  expect(findNewerSchedule("a", list)).toBeNull();
});

test("falls back to list position when rows carry no created_at", () => {
  const list = [{ id: "a" }, { id: "b" }, { id: "c" }];
  expect(findNewerSchedule("a", list)).toBe("c");
  expect(findNewerSchedule("c", list)).toBeNull();
});

test("bound id absent from the listing → null", () => {
  expect(findNewerSchedule("missing", [s("a", "2026-01-05T09:00:00Z")])).toBeNull();
  expect(findNewerSchedule("a", [])).toBeNull();
  expect(findNewerSchedule("a", null)).toBeNull();
});
