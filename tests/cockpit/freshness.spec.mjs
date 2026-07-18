// Pure-logic regression for the newer-schedule detection (Session 4.3 CU6). No
// rendering — runs once, theme-free, in the `logic` project (like legality /
// rowstats). Pins findNewerSchedule so the stale-tab "a newer schedule exists"
// offer only ever fires for a strictly-newer LIVE schedule of the SAME
// submission, and never guesses when the scope is unknown.
import { test, expect } from "@playwright/test";
import { findNewerSchedule } from "../../src/cockpit/src/freshness.js";

// listing rows are ordered oldest→newest (created_at asc), scenarios excluded.
const rows = (...xs) => xs;
const s = (id, submission_id, status = "proposed") => ({ id, submission_id, status });

test("returns the newest same-submission live schedule strictly newer than the bound one", () => {
  const list = rows(
    s("a", "sub-1"), s("b", "sub-1"), s("c", "sub-1"),
  );
  expect(findNewerSchedule("a", list)).toBe("c");   // newest after a
  expect(findNewerSchedule("b", list)).toBe("c");
  expect(findNewerSchedule("c", list)).toBeNull();  // already newest
});

test("never crosses submission scope — a newer DIFFERENT-submission schedule is not offered", () => {
  const list = rows(s("a", "sub-1"), s("z", "sub-2"), s("y", "sub-2"));
  expect(findNewerSchedule("a", list)).toBeNull();
});

test("mixed scopes: only same-submission successors count", () => {
  const list = rows(
    s("a", "sub-1"), s("x", "sub-2"), s("b", "sub-1"), s("y", "sub-2"),
  );
  expect(findNewerSchedule("a", list)).toBe("b");
});

test("skips a superseded successor (never routes to a dead version)", () => {
  const list = rows(s("a", "sub-1"), s("b", "sub-1", "superseded"));
  expect(findNewerSchedule("a", list)).toBeNull();
  const list2 = rows(s("a", "sub-1"), s("b", "sub-1", "superseded"), s("c", "sub-1"));
  expect(findNewerSchedule("a", list2)).toBe("c");
});

test("unknown scope (no submission_id) never guesses", () => {
  const list = rows({ id: "a" }, { id: "b" });
  expect(findNewerSchedule("a", list)).toBeNull();
});

test("bound id absent from the listing → null", () => {
  expect(findNewerSchedule("missing", rows(s("a", "sub-1")))).toBeNull();
  expect(findNewerSchedule("a", [])).toBeNull();
  expect(findNewerSchedule("a", null)).toBeNull();
});
