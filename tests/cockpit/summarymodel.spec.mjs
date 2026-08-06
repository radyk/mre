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
  sourcesOf, STORED_SOURCES, STAT_GAPS,
} from "../../src/cockpit/src/summarymodel.js";

const trail = (...objs) => objs.map((o, i) => ({
  index: i + 1, objective: o, elapsed_s: 0.1 * (i + 1),
}));

// A document with a trail, as the assembler builds one.
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

test("the three unsourceable statistics are NAMED, not computed and not dropped", () => {
  // The brief asked for late/on-time counts, utilization by machine and total
  // changeover minutes. None is stored. An honest gap beats a number with no
  // provenance — and a gap that is silently dropped is neither.
  const s = statsModel(withTrail());
  expect(s.gaps.map((g) => g.key)).toEqual(
    ["late_counts", "utilization", "changeover"]);
  for (const g of s.gaps) {
    expect(g.why.length).toBeGreaterThan(10);
    expect(g.from.length).toBeGreaterThan(10);   // where it SHOULD come from
  }
});

test("the model never counts late orders itself", () => {
  // The document carries per-order lateness; tallying it here would be exactly
  // the frontend computation the gap exists to refuse.
  const doc = withTrail();
  doc.service_outcomes = [{ lateness_min: 10 }, { lateness_min: -5 }];
  const keys = statsModel(doc).stats.map((x) => x.key);
  expect(keys).not.toContain("late");
  expect(keys).not.toContain("late_counts");
});

// ---------------------------------------------------------------------------
// THE PROVENANCE GUARD
// ---------------------------------------------------------------------------

test("every figure the model produces names a stored document field", () => {
  const doc = withTrail();
  doc.solver.portfolio = { k: 3, seed0: 42, winner_seed: 44, members: [] };
  const used = sourcesOf(summaryModel(doc));
  expect(used.length).toBeGreaterThan(0);
  for (const src of used) {
    expect(STORED_SOURCES,
      `${src} is not a declared stored source — a figure was computed here`)
      .toContain(src);
  }
});

test("a monolithic document yields no rolling counts and no crash", () => {
  const doc = withTrail();
  delete doc.rolling;
  const m = summaryModel(doc);
  expect(m.stats.stats.map((s) => s.key))
    .toEqual(["tardiness", "tardiness_floor", "setup"]);
  expect(m.stats.gaps).toHaveLength(STAT_GAPS.length);
});
