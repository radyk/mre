// THE SUMMARY SCREEN's MODEL (Session W2.1, R-SP1). PURE — no DOM, no fetch,
// no arithmetic the server did not already do. It runs in the Playwright
// "logic" project, which has no browser, and that is deliberate: the rule this
// screen is built under is that EVERY figure it shows is read from a stored
// field of the schedule document, so the module that decides what is shown must
// be testable without rendering anything.
//
// THE DISCIPLINE, STATED SO A LATER READER CANNOT MISS IT. The brief for this
// screen forbids computing a statistic frontend-side or bolting a backend
// calculation on in passing: an honest gap beats a number with no provenance.
// So every entry this module produces carries `source` — the document path it
// came from — and every statistic we CANNOT source appears in `gaps` with the
// reason and where it should come from instead. `sourcesOf()` exists so a test
// can assert the whole rendered set against the document's own field names; if
// someone later computes a figure here, its source string is the thing that
// will not exist.

/** Document paths this module is allowed to read. One list, asserted by test. */
export const STORED_SOURCES = [
  "cost_summary.total",
  "cost_summary.production_regular",
  "cost_summary.production_overtime",
  "cost_summary.setup",
  "cost_summary.tardiness",
  "cost_summary.tardiness_floor",
  "cost_summary.tardiness_controllable",
  "solver.portfolio",
  "solver.progress",
  "solver.status",
  "solver.gap",
  "rolling.committed_count",
  "rolling.active_count",
  "rolling.beyond_horizon",
];

// The statistics the v1 row was asked for that NO artifact currently stores.
// Rendered as named gaps, never as computed numbers. Each names where it should
// come from — the fix is a backend rollup, not a client-side sum.
export const STAT_GAPS = [
  {
    key: "late_counts",
    label: "late / on-time orders",
    why: "no count is stored — the document carries per-order lateness, not a tally",
    from: "an M7 extractor rollup (service.late_demands / service.on_time_demands) "
        + "beside the per-demand lateness_minutes metric it already emits",
  },
  {
    key: "utilization",
    label: "utilization by machine",
    why: "no board-scope figure is stored — the board's own utilization is "
       + "recomputed per visible window as the planner pans, and a figure over "
       + "one denominator is not the figure over another",
    from: "an M7 rollup that names its denominator (working minutes over open "
        + "capacity, for a stated span)",
  },
  {
    key: "changeover",
    label: "total changeover minutes",
    why: "no total is stored — setup minutes are carried per bar",
    from: "an M7 rollup beside the setup COST the ledger already decomposes",
  },
];

const num = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);

/** The money block: the ledger and its stored decomposition. */
export function moneyModel(doc) {
  const cs = (doc && doc.cost_summary) || null;
  if (!cs) return null;
  const rows = [
    ["production (regular)", num(cs.production_regular), "cost_summary.production_regular"],
    ["production (overtime)", num(cs.production_overtime), "cost_summary.production_overtime"],
    ["setup", num(cs.setup), "cost_summary.setup"],
    ["tardiness", num(cs.tardiness), "cost_summary.tardiness"],
  ].filter((r) => r[1] !== null).map(([label, value, source]) => ({ label, value, source }));
  // R-PD1 clause (4): the split DECOMPOSES tardiness, it does not add to it, and
  // it is all-or-nothing (the contract validator enforces both-or-neither), so
  // it renders as a sub-row of tardiness and never as another line in the total.
  const floor = num(cs.tardiness_floor);
  const controllable = num(cs.tardiness_controllable);
  return {
    total: num(cs.total),
    totalSource: "cost_summary.total",
    rows,
    split: floor === null ? null : {
      floor, controllable,
      floorSource: "cost_summary.tardiness_floor",
      controllableSource: "cost_summary.tardiness_controllable",
    },
  };
}

/** The R-BK1 portfolio story, or null at K=1 (where the block is absent). */
export function portfolioModel(doc) {
  const p = doc && doc.solver && doc.solver.portfolio;
  if (!p) return null;
  return {
    k: p.k,
    declaration: p.declaration || "",
    winnerSeed: p.winner_seed ?? null,
    winnerTotal: num(p.winner_ledger_total),
    // R-BK1 clause (4): a spread of one number is None, never 0.00 — so null
    // here renders as "not enough publishable members to state a spread", never
    // as agreement nobody observed.
    spreadPct: num(p.spread_pct),
    spreadAbs: num(p.spread_abs),
    agreement: p.agreement || "",
    unpublished: p.unpublished || "",
    members: (p.members || []).map((m) => ({
      seed: m.seed,
      ledgerTotal: num(m.ledger_total),
      selectable: m.selectable !== false,
      reason: m.reason || "",
      status: m.status || "",
    })),
    source: "solver.portfolio",
  };
}

/**
 * The R-SP1 solve-progress story. THREE STATES, all honest:
 *
 *   absent  the board was solved before the solver kept a search history.
 *           Clause (5): boards solved before the change have no trail and never
 *           will, so this is a permanent state and not a loading one.
 *   flat    exactly one incumbent. Clause (4): a flat story is a true story.
 *   present more than one incumbent.
 *
 * All authored COPY except the absent state's comes from the server block —
 * `headline`, `clause_2_label`, `clause_3_label` are composed once in
 * `mre.modules.solve_progress` so the cockpit and the answer surfaces cannot
 * state different things. The absent state has no block by definition, so its
 * sentence is the one this module owns, and it makes no claim about the search.
 */
export function progressModel(doc) {
  const p = doc && doc.solver && doc.solver.progress;
  if (!p) {
    return {
      state: "absent",
      sentence: "This plan was solved before the solver kept a record of its "
              + "own search, so there is no progress history for it. Nothing "
              + "was reconstructed in its place.",
      source: "solver.progress",
    };
  }
  const state = (p.count || 0) === 0 ? "none" : (p.flat ? "flat" : "present");
  return {
    state,
    sentence: p.headline || "",
    clause2: p.clause_2_label || "",
    clause3: p.clause_3_label || "",
    stage: p.stage || "",
    windowKey: p.window_key ?? null,
    unit: p.objective_unit || "",
    count: p.count || 0,
    first: num(p.first),
    final: num(p.final),
    improvementPct: num(p.improvement_pct),
    bestBound: num(p.best_bound),
    gap: num(p.gap),
    incumbents: (p.incumbents || []).map((i) => ({
      index: i.index, objective: num(i.objective), elapsedS: num(i.elapsed_s),
    })),
    source: "solver.progress",
  };
}

/** The v1 statistics row: what IS stored, plus the named gaps for what is not. */
export function statsModel(doc) {
  const cs = (doc && doc.cost_summary) || {};
  const rolling = (doc && doc.rolling) || null;
  const stats = [];
  if (num(cs.tardiness) !== null) {
    stats.push({ key: "tardiness", label: "tardiness cost", kind: "money",
                 value: cs.tardiness, source: "cost_summary.tardiness" });
  }
  if (num(cs.tardiness_floor) !== null) {
    stats.push({ key: "tardiness_floor", label: "…of which unavoidable",
                 kind: "money", value: cs.tardiness_floor,
                 source: "cost_summary.tardiness_floor" });
  }
  if (num(cs.setup) !== null) {
    stats.push({ key: "setup", label: "changeover cost", kind: "money",
                 value: cs.setup, source: "cost_summary.setup" });
  }
  if (rolling) {
    stats.push({ key: "committed", label: "committed operations", kind: "count",
                 value: rolling.committed_count || 0,
                 source: "rolling.committed_count" });
    stats.push({ key: "active", label: "operations in this window",
                 kind: "count", value: rolling.active_count || 0,
                 source: "rolling.active_count" });
    stats.push({ key: "tray", label: "orders beyond the horizon", kind: "count",
                 value: (rolling.beyond_horizon || []).length,
                 source: "rolling.beyond_horizon" });
  }
  return { stats, gaps: STAT_GAPS };
}

/** The whole screen's model. */
export function summaryModel(doc) {
  return {
    scheduleId: (doc && doc.schedule_id) || null,
    status: (doc && doc.solver && doc.solver.status) || null,
    money: moneyModel(doc),
    portfolio: portfolioModel(doc),
    progress: progressModel(doc),
    stats: statsModel(doc),
  };
}

/** Every document path the model actually read, for the provenance guard. */
export function sourcesOf(model) {
  const out = new Set();
  if (model.money) {
    out.add(model.money.totalSource);
    model.money.rows.forEach((r) => out.add(r.source));
    if (model.money.split) {
      out.add(model.money.split.floorSource);
      out.add(model.money.split.controllableSource);
    }
  }
  if (model.portfolio) out.add(model.portfolio.source);
  if (model.progress) out.add(model.progress.source);
  model.stats.stats.forEach((s) => out.add(s.source));
  return [...out];
}
