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
  // contract 1.17 (Session W2.2) — the three rollups W2.1 named as gaps
  "statistics.late_demands",
  "statistics.on_time_demands",
  "statistics.changeover_minutes",
  "statistics.utilization_by_resource",
];

// W2.1 rendered three asked-for statistics as NAMED GAPS because nothing stored
// them. Session W2.2 landed the M7 rollups, so the gap list is now EMPTY — and
// it stays in the code, exported and asserted, rather than being deleted. Two
// reasons: the screen must keep the machinery to name a gap the next time one
// appears, and a reader of this file should be able to see that the gaps were
// closed by a rollup rather than quietly replaced by a client-side sum.
export const STAT_GAPS = [];

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
    // R-SP1 AMENDMENT 1 (contract 1.17). `priced` is TRUE only when both
    // endpoints are ledger-priced placements; a trail recorded before the
    // amendment, or one whose first incumbent was never captured, is FALSE and
    // renders the objective-space percentage exactly as it did before. Three
    // generations of trail, each honest — so this is a state, never a fallback
    // that pretends to be the real thing.
    priced: p.priced === true,
    firstPlanCost: num(p.first_plan_cost),
    finalPlanCost: num(p.final_plan_cost),
    dollarImprovementAbs: num(p.dollar_improvement_abs),
    dollarImprovementPct: num(p.dollar_improvement_pct),
    // The amendment's wall-cost disclosure. Non-empty only where it applies.
    captureNote: p.capture_note || "",
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

/**
 * Per-machine utilization (contract 1.17, W2.2 B2).
 *
 * Rendered as its own list rather than a tile, because a ratio without its
 * denominator is the 4B.20 defect and a tile has nowhere to put one. Every row
 * carries the working minutes and the open capacity it was computed from, and
 * the block carries the server's own definition string — the cockpit never
 * words it, so it cannot re-imply a denominator of its own.
 *
 * A resource whose utilization is null (no calendar, or no open capacity) keeps
 * its row and states that there is no denominator. Dropping it would make the
 * list read as "every machine we could measure" when it is not.
 */
export function utilizationModel(doc) {
  const s = (doc && doc.statistics) || null;
  const by = s && s.utilization_by_resource;
  if (!by || !Object.keys(by).length) return null;
  const nameOf = (rid) => {
    const lane = ((doc && doc.resources) || []).find((r) => r.resource_id === rid);
    return (lane && lane.external_name) || rid;   // never invent a name
  };
  const rows = Object.entries(by).map(([rid, u]) => ({
    resourceId: rid,
    name: nameOf(rid),
    workingMinutes: num(u.working_minutes),
    openCapacityMinutes: num(u.open_capacity_minutes),
    utilization: num(u.utilization),
  }));
  // busiest first, so the thing a planner needs is at the top; rows with no
  // ratio sort last rather than sorting as zero.
  rows.sort((a, b) => (b.utilization ?? -1) - (a.utilization ?? -1));
  return { rows, definition: s.utilization_definition || "",
           source: "statistics.utilization_by_resource" };
}

/** The v1 statistics row: what IS stored, plus the named gaps for what is not. */
export function statsModel(doc) {
  const cs = (doc && doc.cost_summary) || {};
  const rolling = (doc && doc.rolling) || null;
  const st = (doc && doc.statistics) || null;
  const stats = [];
  // W2.2 B1 — the count W2.1 refused to tally client-side. It is now a stored
  // rollup, so it renders as a figure. It stays DISTINCT from the tardiness
  // split below: one is a count of orders, the other decomposes a charge.
  if (st && num(st.late_demands) !== null) {
    stats.push({ key: "late", label: "orders finishing late", kind: "count",
                 value: st.late_demands, source: "statistics.late_demands" });
    stats.push({ key: "on_time", label: "orders on time or early",
                 kind: "count", value: st.on_time_demands,
                 source: "statistics.on_time_demands" });
  }
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
  // W2.2 B3. Beside the changeover COST, deliberately: the two are billed over
  // the same WIP-filtered operation set, and showing them together is what
  // makes that checkable rather than merely documented.
  if (st && num(st.changeover_minutes) !== null) {
    stats.push({ key: "changeover", label: "changeover minutes", kind: "count",
                 value: st.changeover_minutes,
                 source: "statistics.changeover_minutes" });
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
    utilization: utilizationModel(doc),
  };
}

/**
 * Every document path the model actually read, for the provenance guard.
 *
 * WALKED, NOT ENUMERATED (Session W2.2). The first version listed four branches
 * by hand — money, portfolio, progress, stats — and the W2.2 predicate audit
 * found the consequence before the figures landed: any figure added OUTSIDE
 * those four would have passed "every figure names a stored field" by never
 * being looked at. A guard whose coverage has to be maintained by hand is a
 * guard that silently narrows every time the thing it guards grows.
 *
 * So this walks the whole model for keys named `source` or `*Source`. A new
 * branch is covered by existing, and a figure that forgets its source string is
 * caught by the companion assertion (`unsourcedFigures`) rather than by being
 * invisible here.
 */
export function sourcesOf(model) {
  const out = new Set();
  const walk = (node) => {
    if (node == null || typeof node !== "object") return;
    if (Array.isArray(node)) { node.forEach(walk); return; }
    for (const [k, v] of Object.entries(node)) {
      if ((k === "source" || k.endsWith("Source")) && typeof v === "string" && v) {
        out.add(v);
      } else {
        walk(v);
      }
    }
  };
  walk(model);
  return [...out];
}

/**
 * Model branches that produce a FIGURE but name no source — the other half of
 * the provenance rule. `sourcesOf` proves that what we cite is stored;
 * this proves there is nothing we show that we did not cite.
 *
 * A "figure-bearing" node is one carrying a numeric `value` (a stat tile) or a
 * numeric `utilization` (a machine row). Both shapes must carry a source, and
 * the utilization rows inherit theirs from the block they belong to.
 */
export function unsourcedFigures(model) {
  const bad = [];
  for (const s of model.stats.stats) {
    if (typeof s.value === "number" && !s.source) bad.push(s.key || "(unnamed)");
  }
  if (model.utilization && !model.utilization.source) bad.push("utilization");
  if (model.money && model.money.total != null && !model.money.totalSource) {
    bad.push("money.total");
  }
  return bad;
}
