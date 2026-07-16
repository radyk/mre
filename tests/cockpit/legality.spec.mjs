// Tier-0 legality library tests (CU2, docs/04 R-DP6). Pure-JS: they import the
// framework-free module directly and feed it (a) HAND-BUILT payloads with
// hand-verified expected zones and (b) the committed multi_route fixtures.
//
// The four dim dimensions each get at least one case, per the brief:
//   * capability dim         — an ineligible row is never green
//   * closed-calendar dim    — a start inside a closure is never green
//   * precedence-floor dim   — a start before the predecessor finish is dim
//   * window-fit dim (resumable) — a start with < duration open capacity ahead
//                                  is dim even for a resumable op
// plus the conservative-error invariant (R-DP6): the library may UNDER-offer
// green but must NEVER green a proven-illegal spot.
import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { buildContext, computeTier0, isLegalStart } from "../../src/cockpit/legality/tier0.js";

const FIX = resolve(dirname(fileURLToPath(import.meta.url)), "fixtures");
const load = (name) => JSON.parse(readFileSync(resolve(FIX, name), "utf-8"));

// --- a fully controlled synthetic world (hand-verified numbers) ------------
// R-A: 08:00–12:00 open, 12:00–13:00 CLOSED, 13:00–17:00 open (two 4h windows).
// R-B: 08:00–17:00 open (one 9h window).
const D = "2026-03-02";
// normalize to the canonical ISO form the library emits (millis included)
const at = (hhmm) => new Date(`${D}T${hhmm}:00Z`).toISOString();
const W = (kind, s, e) => ({ kind, start: at(s), end: at(e) });

function synthDoc(assignments = []) {
  return {
    horizon: { start: `${D}T00:00:00Z`, end: "2026-03-03T00:00:00Z" },
    resources: [
      { resource_id: "R-A", external_name: "A", calendar_windows: [
        W("regular", "08:00", "12:00"), W("closure", "12:00", "13:00"),
        W("regular", "13:00", "17:00")] },
      { resource_id: "R-B", external_name: "B", calendar_windows: [
        W("regular", "08:00", "17:00")] },
    ],
    assignments,
  };
}

// one op, eligible + duration + resumable configurable, optional predecessor.
function synthInteraction(op) {
  return { operations: [op], precedence_edges: op._edges || [] };
}

test("capability dim — an ineligible row is never green", () => {
  const doc = synthDoc();
  const inter = synthInteraction({
    operation_ref: "OP1", eligible_resource_ids: ["R-A"],
    working_min: 60, setup_min: 0, earliest_start: null, resumable: false,
  });
  const t0 = computeTier0("OP1", buildContext(doc, inter));
  const rowB = t0.rows.find((r) => r.resource_id === "R-B");
  expect(rowB.eligible).toBe(false);
  expect(rowB.reason).toBe("capability");
  expect(rowB.legal_regions).toHaveLength(0);
  // and the eligible row DOES offer green
  const rowA = t0.rows.find((r) => r.resource_id === "R-A");
  expect(rowA.eligible).toBe(true);
  expect(rowA.legal_regions.length).toBeGreaterThan(0);
});

test("three row-types (R-DP2 takes/dims/dims) — eligible, capability-dim, solver-pruned", () => {
  // Session 4.0b: eligible_resource_ids is now the solver-PINNABLE set. A
  // capability-eligible resource the solver pruned (no op_assign literal, e.g.
  // no in-horizon calendar window for a resumable op) is ABSENT from it and
  // named in dim_reasons, so Tier-0 dims it with the truth — never greens a row
  // the R-DP1 pin would silently skip. Three rows, one of each kind:
  //   R-A eligible → takes (green offered, a legal start is legal)
  //   R-B capability-ineligible → dims ("capability")
  //   R-C solver-pruned → dims ("no_calendar_window"), NOT greened
  const doc = synthDoc();
  doc.resources.push({ resource_id: "R-C", external_name: "C",
    calendar_windows: [W("regular", "08:00", "17:00")] });  // R-C's calendar is OPEN
  const ctx = buildContext(doc, synthInteraction({
    operation_ref: "OP1", eligible_resource_ids: ["R-A"],
    dim_reasons: { "R-C": "no_calendar_window" },
    working_min: 60, setup_min: 0, resumable: false,
  }));
  const t0 = computeTier0("OP1", ctx);
  const row = (rid) => t0.rows.find((r) => r.resource_id === rid);

  // R-A: takes — eligible, offers green, a legal start is legal.
  expect(row("R-A").eligible).toBe(true);
  expect(row("R-A").legal_regions.length).toBeGreaterThan(0);
  expect(isLegalStart("OP1", "R-A", at("09:00"), ctx).legal).toBe(true);

  // R-B: dims — capability-ineligible (absent, no dim_reasons entry → default).
  expect(row("R-B").eligible).toBe(false);
  expect(row("R-B").reason).toBe("capability");
  expect(row("R-B").legal_regions).toHaveLength(0);
  expect(isLegalStart("OP1", "R-B", at("09:00"), ctx)).toEqual({ legal: false, reason: "capability" });

  // R-C: dims — solver-pruned despite an OPEN calendar; the reason is the
  // payload's truth, and the drop is refused (never greened).
  expect(row("R-C").eligible).toBe(false);
  expect(row("R-C").reason).toBe("no_calendar_window");
  expect(row("R-C").legal_regions).toHaveLength(0);
  expect(isLegalStart("OP1", "R-C", at("09:00"), ctx)).toEqual({ legal: false, reason: "no_calendar_window" });
});

test("closed-calendar dim — a start inside a closure is never green", () => {
  const doc = synthDoc();
  const ctx = buildContext(doc, synthInteraction({
    operation_ref: "OP1", eligible_resource_ids: ["R-A", "R-B"],
    working_min: 60, setup_min: 0, resumable: false,
  }));
  // 60-min op on R-A: window1 → start [08:00,11:00]; window2 → start [13:00,16:00].
  const t0 = computeTier0("OP1", ctx);
  const rowA = t0.rows.find((r) => r.resource_id === "R-A");
  expect(rowA.legal_regions).toEqual([
    { start: at("08:00"), end: at("11:00") },
    { start: at("13:00"), end: at("16:00") },
  ]);
  // a start at 12:30 (inside the closure) is proven illegal
  expect(isLegalStart("OP1", "R-A", at("12:30"), ctx).legal).toBe(false);
  // no legal region contains any point of the closure
  for (const r of rowA.legal_regions) {
    expect(Date.parse(r.end) <= Date.parse(at("12:00")) ||
           Date.parse(r.start) >= Date.parse(at("13:00"))).toBe(true);
  }
});

test("precedence-floor dim — a start before the predecessor finish is dim", () => {
  // predecessor P placed on R-B ending at 10:00; successor S floors at 10:00.
  const doc = synthDoc([{
    assignment_id: "aP", operation_ref: "P", resource_id: "R-B",
    chunks: [{ start: at("08:00"), end: at("10:00") }],
  }]);
  const op = {
    operation_ref: "S", eligible_resource_ids: ["R-A"],
    working_min: 60, setup_min: 0, resumable: false,
    _edges: [{ predecessor_ref: "P", successor_ref: "S", min_lag_min: 0 }],
  };
  const ctx = buildContext(doc, synthInteraction(op));
  const t0 = computeTier0("S", ctx);
  expect(t0.floor).toBe(at("10:00"));
  expect(t0.anchors.predecessor_finishes).toContain(at("10:00"));
  const rowA = t0.rows.find((r) => r.resource_id === "R-A");
  // window1 legal start now floored to 10:00, not 08:00
  expect(rowA.legal_regions[0]).toEqual({ start: at("10:00"), end: at("11:00") });
  // a start at 09:00 (before the floor) is proven illegal, reason precedence
  expect(isLegalStart("S", "R-A", at("09:00"), ctx)).toEqual({ legal: false, reason: "precedence_floor" });
});

test("window-fit dim (resumable) — too-late a start is dim even when it may span closures", () => {
  const doc = synthDoc();
  // 300-min (5h) op. R-A has two 4h windows (8h total open across the closure).
  const resumable = buildContext(doc, synthInteraction({
    operation_ref: "OP1", eligible_resource_ids: ["R-A", "R-B"],
    working_min: 300, setup_min: 0, resumable: true,
  }));
  const t0r = computeTier0("OP1", resumable);
  const rowAr = t0r.rows.find((r) => r.resource_id === "R-A");
  // it FITS across the closure, but only if started by 11:00 (need 1h left in
  // window1 + all 4h of window2 = 5h). Latest legal start = 11:00.
  expect(rowAr.legal_regions).toEqual([{ start: at("08:00"), end: at("11:00") }]);
  expect(isLegalStart("OP1", "R-A", at("11:30"), resumable).legal).toBe(false); // window-fit
  expect(isLegalStart("OP1", "R-A", at("10:00"), resumable).legal).toBe(true);

  // the SAME op non-resumable cannot fit either 4h window at all → R-A all dim
  // (the contrast that makes "resumable" mean something).
  const nonres = buildContext(doc, synthInteraction({
    operation_ref: "OP1", eligible_resource_ids: ["R-A", "R-B"],
    working_min: 300, setup_min: 0, resumable: false,
  }));
  const rowAn = computeTier0("OP1", nonres).rows.find((r) => r.resource_id === "R-A");
  expect(rowAn.legal_regions).toHaveLength(0);
  // both agree R-B (9h contiguous) fits
  expect(computeTier0("OP1", nonres).rows.find((r) => r.resource_id === "R-B").legal_regions.length).toBeGreaterThan(0);
});

// --- fixture-driven: real multi_route data ---------------------------------
test("multi_route fixture — capability dim + conservative-error hold on real data", () => {
  const doc = load("schedule.json");
  const interaction = load("interaction.json").interaction;
  const ctx = buildContext(doc, interaction);
  const nRes = doc.resources.length;

  // a real op eligible on a STRICT subset of the machines (multi_route seq20 =
  // {R0,R1}), so some rows must be dim-by-capability.
  const partial = interaction.operations.find((o) => o.eligible_resource_ids.length < nRes);
  expect(partial, "multi_route has an op eligible on a subset of machines").toBeTruthy();
  const t0 = computeTier0(partial.operation_ref, ctx);
  expect(t0.rows).toHaveLength(nRes);
  const eligibleSet = new Set(partial.eligible_resource_ids);
  for (const row of t0.rows) {
    if (!eligibleSet.has(row.resource_id)) {
      expect(row.eligible).toBe(false);
      expect(row.legal_regions).toHaveLength(0);
    }
  }

  // conservative-error (R-DP6): on an eligible row, every legal region starts
  // at/after the floor, and an overnight (closed) start is proven illegal —
  // the library never greens a spot canonical arithmetic rejects.
  const eligibleRow = t0.rows.find((r) => r.eligible && r.legal_regions.length);
  expect(eligibleRow, "at least one eligible row offers green").toBeTruthy();
  if (t0.floor) {
    for (const r of eligibleRow.legal_regions) {
      expect(Date.parse(r.start)).toBeGreaterThanOrEqual(Date.parse(t0.floor));
    }
  }
  // 03:00 UTC is outside the 07:00–19:00 working calendar → dim
  const anyOpen = eligibleRow.legal_regions[0].start.slice(0, 10);
  expect(isLegalStart(partial.operation_ref, eligibleRow.resource_id, `${anyOpen}T03:00:00Z`, ctx).legal).toBe(false);
});
