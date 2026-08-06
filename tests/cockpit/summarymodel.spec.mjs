// THE SUMMARY SCREEN's MODEL (Session W2.1, R-SP1) — pure, no browser.
//
// This file guards the rule the screen is built under: every figure it shows is
// a STORED field of the schedule document, and every statistic that is not
// stored is a NAMED GAP rather than a client-side computation. The provenance
// test at the bottom is the one that actually enforces it — if someone later
// computes a number here, it will have no `source` and the assertion fails.
import { test, expect } from "@playwright/test";
import {
  summaryModel, progressModel, moneyModel, portfolioModel, statsModel,
  utilizationModel, sourcesOf, unsourcedFigures, STORED_SOURCES, STAT_GAPS,
} from "../../src/cockpit/src/summarymodel.js";

const trail = (...objs) => objs.map((o, i) => ({
  index: i + 1, objective: o, elapsed_s: 0.1 * (i + 1),
}));

// A document with a trail, as the assembler builds one.
// A contract-1.17 document: priced trail + the three rollups.
const withStats = () => {
  const d = withTrail();
  d.solver.progress = {
    ...d.solver.progress,
    priced: true, first_plan_cost: 18905.42, final_plan_cost: 10304.58,
    dollar_improvement_abs: 8600.84, dollar_improvement_pct: 45.5,
    capture_note: "",
    headline: "The solver's first workable plan would have cost $18,905.42; "
            + "the plan it finished on costs $10,304.58 - 45.5% less.",
  };
  d.statistics = {
    late_demands: 3, on_time_demands: 37, demands_counted: 40,
    changeover_minutes: 220,
    utilization_definition: "working minutes billed on this resource ... divided "
      + "by the open calendar minutes flattened for this resource across the "
      + "solver's planning horizon",
    utilization_by_resource: {
      R1: { working_minutes: 300, open_capacity_minutes: 600, utilization: 0.5 },
      R2: { working_minutes: 120, open_capacity_minutes: null, utilization: null },
    },
  };
  d.resources = [{ resource_id: "R1", external_name: "MILL-01" }];
  return d;
};

const withTrail = (over = {}) => ({
  schedule_id: "rolling-test-000",
  cost_summary: {
    total: 1000, production_regular: 400, production_overtime: 100,
    setup: 100, tardiness: 400, tardiness_floor: 250,
    tardiness_controllable: 150,
  },
  solver: {
    status: "FEASIBLE", gap: 0.1,
    progress: {
      stage: "cost", window_key: "2026-01-12T00:00:00+00:00",
      count: 3, first: 1000, final: 750, improvement_abs: 250,
      improvement_pct: 25, flat: false, best_bound: 700, gap: 0.0667,
      objective_unit: "objective_units",
      headline: "The solver's first workable plan scored 1,000; it finished on "
              + "a plan scoring 750 — 25.0% better by its own cost measure.",
      clause_2_label: "This compares the solver's own first workable plan…",
      clause_3_label: "The figures in this trail are the solver's own internal "
                    + "cost measure, not dollars.",
      incumbents: trail(1000, 900, 750),
    },
  },
  rolling: { committed_count: 4, active_count: 20, beyond_horizon: [1, 2, 3] },
  ...over,
});

// ---------------------------------------------------------------------------
// the three progress states (clause 3/4/5)
// ---------------------------------------------------------------------------

test("progress state: PRESENT — the trail renders from the server's own copy", () => {
  const p = progressModel(withTrail());
  expect(p.state).toBe("present");
  expect(p.count).toBe(3);
  expect(p.incumbents.map((i) => i.objective)).toEqual([1000, 900, 750]);
  expect(p.improvementPct).toBe(25);
  // Clause (1): the trail names the ONE window it belongs to.
  expect(p.windowKey).toBe("2026-01-12T00:00:00+00:00");
  // Clause (7): stage 1, the COST search.
  expect(p.stage).toBe("cost");
});

test("progress state: FLAT — one incumbent is a true story, not an absent one", () => {
  const doc = withTrail();
  doc.solver.progress = {
    ...doc.solver.progress, count: 1, flat: true, final: 1000,
    improvement_abs: 0, improvement_pct: 0, incumbents: trail(1000),
    headline: "The solver found one workable plan, scoring 1,000 on its own "
            + "cost measure, and did not improve on it within its budget.",
  };
  const p = progressModel(doc);
  expect(p.state).toBe("flat");
  expect(p.sentence).toContain("did not improve");
});

test("progress state: ABSENT — a pre-change board says so and claims nothing", () => {
  const doc = withTrail();
  delete doc.solver.progress;
  const p = progressModel(doc);
  expect(p.state).toBe("absent");
  // Clause (5): boards solved before the change have no trail and never will,
  // so the copy must not read as "loading" or as an error.
  expect(p.sentence).toContain("before the solver kept a record");
  expect(p.sentence).toContain("Nothing was reconstructed");
});

test("progress state: NONE — a solve that found nothing has no first plan", () => {
  const doc = withTrail();
  doc.solver.progress = { ...doc.solver.progress, count: 0, incumbents: [], first: null, final: null };
  expect(progressModel(doc).state).toBe("none");
});

// ---------------------------------------------------------------------------
// R-DP12 / R-SP1 clause (3): the trail is not money
// ---------------------------------------------------------------------------

test("no trail figure is labelled as currency", () => {
  const p = progressModel(withTrail());
  expect(p.unit).toBe("objective_units");
  expect(p.unit).not.toContain("$");
  // the model must not invent a dollar field on the trail
  expect(Object.keys(p)).not.toContain("dollars");
});

// ---------------------------------------------------------------------------
// the money block (dollars first) and R-BK1
// ---------------------------------------------------------------------------

test("the money block reads the ledger and its stored decomposition", () => {
  const m = moneyModel(withTrail());
  expect(m.total).toBe(1000);
  expect(m.rows.map((r) => r.label)).toEqual([
    "production (regular)", "production (overtime)", "setup", "tardiness"]);
  // R-PD1 clause (4): the split DECOMPOSES tardiness and is all-or-nothing.
  expect(m.split.floor + m.split.controllable).toBe(400);
});

test("the tardiness split is absent, not halved, on a board with no past due", () => {
  const doc = withTrail();
  doc.cost_summary.tardiness_floor = null;
  doc.cost_summary.tardiness_controllable = null;
  expect(moneyModel(doc).split).toBeNull();
});

test("portfolio: absent at K=1, and a one-member spread is null not zero", () => {
  expect(portfolioModel(withTrail())).toBeNull();      // no block at K=1
  const doc = withTrail();
  doc.solver.portfolio = {
    k: 3, seed0: 42, winner_seed: 44, winner_ledger_total: 1000,
    spread_pct: null, spread_abs: null, declaration: "best of 3 seeded searches",
    members: [{ seed: 42, ledger_total: 1200 }, { seed: 43, ledger_total: null,
      reason: "this seed did not finish", selectable: false },
      { seed: 44, ledger_total: 1000 }],
  };
  const p = portfolioModel(doc);
  expect(p.winnerSeed).toBe(44);
  // R-BK1 clause (4): a losing member is still PUBLISHED, with its reason.
  expect(p.members).toHaveLength(3);
  expect(p.members[1].ledgerTotal).toBeNull();
  expect(p.members[1].reason).toContain("did not finish");
  // a spread of one number is null — never 0.00, which would claim agreement
  expect(p.spreadPct).toBeNull();
});

test("the portfolio winner's total is the ledger the money block states", () => {
  // "provably the same source": the summary must not state one total in the
  // money line and another in the portfolio row.
  const doc = withTrail();
  doc.solver.portfolio = { k: 3, seed0: 42, winner_seed: 44,
    winner_ledger_total: doc.cost_summary.total, members: [] };
  const m = summaryModel(doc);
  expect(m.portfolio.winnerTotal).toBe(m.money.total);
});

// ---------------------------------------------------------------------------
// the v1 statistics row, and the honest gaps
// ---------------------------------------------------------------------------

test("the statistics row renders only stored figures", () => {
  const s = statsModel(withTrail());
  const keys = s.stats.map((x) => x.key);
  expect(keys).toEqual(["tardiness", "tardiness_floor", "setup",
                        "committed", "active", "tray"]);
  expect(s.stats.every((x) => typeof x.source === "string" && x.source.length))
    .toBe(true);
});

test("W2.2 - the three named gaps are CLOSED by rollups, not by a client-side sum", () => {
  // W2.1 named three gaps because nothing stored them. W2.2 landed the M7
  // rollups, so the list is empty - and the machinery stays, so the screen can
  // still name the next gap that appears.
  const s = statsModel(withStats());
  expect(s.gaps).toEqual([]);
  expect(STAT_GAPS).toEqual([]);
  const keys = s.stats.map((x) => x.key);
  expect(keys).toContain("late");
  expect(keys).toContain("on_time");
  expect(keys).toContain("changeover");
});

test("the model still never tallies late orders itself", () => {
  // The count now comes from `statistics`. A document with per-order outcomes
  // but NO rollup must still refuse to tally them - that was the whole rule,
  // and landing the rollup does not license the client-side sum.
  const doc = withTrail();                       // no `statistics` block
  doc.service_outcomes = [{ lateness_min: 10 }, { lateness_min: -5 }];
  const keys = statsModel(doc).stats.map((x) => x.key);
  expect(keys).not.toContain("late");
  expect(keys).not.toContain("on_time");
});

test("late + on-time render as counts, distinct from the tardiness split", () => {
  // R-PD1: one is a COUNT of orders, the other DECOMPOSES a charge. Fusing them
  // is the category error the screen has kept apart since W2.1.
  const m = summaryModel(withStats());
  const late = m.stats.stats.find((s) => s.key === "late");
  expect(late.kind).toBe("count");
  const floor = m.stats.stats.find((s) => s.key === "tardiness_floor");
  expect(floor.kind).toBe("money");
});

test("utilization carries its denominator and both components", () => {
  const u = utilizationModel(withStats());
  expect(u.definition).toContain("open calendar minutes");
  const r = u.rows.find((x) => x.resourceId === "R1");
  expect(r.workingMinutes).toBe(300);
  expect(r.openCapacityMinutes).toBe(600);
  expect(r.utilization).toBeCloseTo(0.5, 6);
  expect(r.name).toBe("MILL-01");            // never a raw UUID on screen
});

test("a machine with no denominator keeps its row and states no ratio", () => {
  // Dropping it would make the list read as "every machine we could measure".
  const u = utilizationModel(withStats());
  const r = u.rows.find((x) => x.resourceId === "R2");
  expect(r).toBeTruthy();
  expect(r.openCapacityMinutes).toBeNull();
  expect(r.utilization).toBeNull();
});

test("utilization is absent, not empty, on a document with no statistics", () => {
  expect(utilizationModel(withTrail())).toBeNull();
});

test("PRICED - both endpoints are dollars and the pair decomposes", () => {
  const p = progressModel(withStats());
  expect(p.priced).toBe(true);
  expect(p.firstPlanCost).toBe(18905.42);
  expect(p.finalPlanCost).toBe(10304.58);
  expect(p.firstPlanCost - p.finalPlanCost).toBeCloseTo(p.dollarImprovementAbs, 2);
});

test("UNPRICED - a pre-amendment trail keeps the objective-space story", () => {
  // Three generations of trail, each honest. `priced: false` is a state, not a
  // fallback pretending to be the real thing.
  const p = progressModel(withTrail());
  expect(p.priced).toBe(false);
  expect(p.firstPlanCost).toBeNull();
  expect(p.improvementPct).toBe(25);       // the percentage still renders
});

test("the wall-cost note is carried only where the server set it", () => {
  expect(progressModel(withStats()).captureNote).toBe("");
  const doc = withStats();
  doc.solver.progress.capture_note = "Capturing the first plan costs a moment";
  expect(progressModel(doc).captureNote).toContain("Capturing");
});

// ---------------------------------------------------------------------------
// THE PROVENANCE GUARD
// ---------------------------------------------------------------------------

test("every figure the model produces names a stored document field", () => {
  const doc = withStats();
  doc.solver.portfolio = { k: 3, seed0: 42, winner_seed: 44, members: [] };
  const used = sourcesOf(summaryModel(doc));
  expect(used.length).toBeGreaterThan(0);
  for (const src of used) {
    expect(STORED_SOURCES,
      `${src} is not a declared stored source — a figure was computed here`)
      .toContain(src);
  }
});

test("...and nothing the model shows is left uncited", () => {
  // The other half of the rule. `sourcesOf` proves what we cite is stored; this
  // proves there is nothing we show that we did not cite.
  expect(unsourcedFigures(summaryModel(withStats()))).toEqual([]);
});

test("THE GUARD WALKS THE MODEL - a new branch is covered by existing", () => {
  // W2.2's predicate audit: the first `sourcesOf` hand-listed four branches, so
  // a figure added outside them would have passed by never being looked at.
  // This asserts the walk reaches a source the enumerated version never would.
  const m = summaryModel(withStats());
  expect(sourcesOf(m)).toContain("statistics.utilization_by_resource");
  const planted = { ...m, someNewBlock: { deep: { thing: { source: "solver.status" } } } };
  expect(sourcesOf(planted)).toContain("solver.status");
});

test("a monolithic document yields no rolling counts and no crash", () => {
  const doc = withTrail();
  delete doc.rolling;
  const m = summaryModel(doc);
  expect(m.stats.stats.map((s) => s.key))
    .toEqual(["tardiness", "tardiness_floor", "setup"]);
  expect(m.stats.gaps).toHaveLength(STAT_GAPS.length);
});
