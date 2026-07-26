// Pure-logic regression for the schedule picker's two reads (hotfix session CU2).
// No rendering — runs once, theme-free, in the `logic` project (like legality /
// rowstats / freshness). Pins the rolling-vs-monolithic tag to the STRUCTURAL
// namings the sliced solve path mints (src/mre/api/app.py `rolling-<run>`;
// rolling_horizon's `snap-rolling`), and the picker's newest-first ordering to a
// stable rule — the listing arrives oldest→newest and ties must not shuffle.
import { test, expect } from "@playwright/test";
import {
  scheduleKind, sortNewestFirst, shortId,
} from "../../src/cockpit/src/schedulepicker.js";

test("a sliced solve's id prefix tags the row rolling", () => {
  // exactly what app.py registers: `rolling-${run_id.slice(0,12)}`
  expect(scheduleKind({ id: "rolling-279dec02-411" })).toBe("rolling");
  // and the harness fixtures, whose ids carry the word in the middle
  expect(scheduleKind({ id: "sched-rolling-fixture" })).toBe("rolling");
  expect(scheduleKind({ id: "sched-rolling-empty" })).toBe("rolling");
});

test("the rolling snapshot naming tags the row even without the id prefix", () => {
  // rolling_horizon.prepare_plant names its snapshot `snap-rolling`
  expect(scheduleKind({ id: "87c705b9-85fc-4788", snapshot_id: "snap-rolling" }))
    .toBe("rolling");
});

test("a monolithic uuid row is monolithic (a uuid cannot spell 'rolling')", () => {
  expect(scheduleKind({ id: "87c705b9-85fc-4788-92c3-f90f9ab1e59a",
                        snapshot_id: "snap-6626502b" })).toBe("monolithic");
  expect(scheduleKind({ id: "sched-multi-route-fixture", snapshot_id: "snap-mr" }))
    .toBe("monolithic");
  expect(scheduleKind(null)).toBe("monolithic");
  expect(scheduleKind({})).toBe("monolithic");
});

test("newest first, by created_at", () => {
  const list = [
    { id: "a", created_at: "2026-01-05T09:00:00Z" },
    { id: "b", created_at: "2026-01-05T10:00:00Z" },
    { id: "c", created_at: "2026-01-05T11:00:00Z" },
  ];
  expect(sortNewestFirst(list).map((r) => r.id)).toEqual(["c", "b", "a"]);
});

test("ties and missing timestamps keep the listing order, reversed (stable)", () => {
  // every committed cockpit fixture shares one created_at — a tie must not
  // shuffle between opens.
  const tied = [
    { id: "a", created_at: "2026-01-05T09:41:00Z" },
    { id: "b", created_at: "2026-01-05T09:41:00Z" },
    { id: "c", created_at: "2026-01-05T09:41:00Z" },
  ];
  expect(sortNewestFirst(tied).map((r) => r.id)).toEqual(["c", "b", "a"]);
  expect(sortNewestFirst(tied).map((r) => r.id)).toEqual(["c", "b", "a"]);
  expect(sortNewestFirst([{ id: "a" }, { id: "b" }]).map((r) => r.id)).toEqual(["b", "a"]);
});

test("rows without an id, and non-arrays, are dropped rather than rendered", () => {
  expect(sortNewestFirst([null, { created_at: "2026-01-05T09:00:00Z" }, { id: "a" }])
    .map((r) => r.id)).toEqual(["a"]);
  expect(sortNewestFirst(null)).toEqual([]);
  expect(sortNewestFirst(undefined)).toEqual([]);
});

test("the short handle truncates a uuid but never invents an ordinal", () => {
  expect(shortId("87c705b9-85fc-4788-92c3-f90f9ab1e59a")).toBe("87c705b9-85f");
  expect(shortId("rolling-279dec02-411")).toBe("rolling-279d");
  expect(shortId("")).toBe("");
});
