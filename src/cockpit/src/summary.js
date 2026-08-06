// THE SUMMARY SCREEN, v1 (Session W2.1, R-SP1). READ-ONLY, DOLLARS FIRST.
//
// One post-solve screen: what this plan costs, what the solver's own search did
// to reach it, and the statistics we can source. It renders FROM RUN ARTIFACTS
// ONLY — every figure is a stored field of the schedule document, selected by
// `summarymodel.js`, which is pure and separately tested. Nothing here computes
// a statistic, and the statistics that no artifact stores are rendered AS NAMED
// GAPS rather than quietly dropped or quietly invented.
//
// PRE/POST IS THE WALL. There is no solve button, no parameter, no Gatehouse
// element on this screen. It describes a solve that has already happened.
//
// R-TZ1: any instant here renders through `clock.js` and the screen states which
// clock that is. R-DP12/R-SP1(3): the trail carries NO dollar sign — its figures
// are the solver's own cost measure, and the only currency on the screen is the
// ledger, which belongs to the finished plan.

import { fmtFull, clockLabel } from "./clock.js";
import { summaryModel } from "./summarymodel.js";

const money = (n) => (n == null ? "—"
  : `$${Math.round(n).toLocaleString("en-US")}`);
// The trail's own unit. Deliberately NOT `money()` — see the header.
const units = (n) => (n == null ? "—" : Math.round(n).toLocaleString("en-US"));
const pct = (n) => (n == null ? "—" : `${n.toFixed(1)}%`);
const secs = (n) => (n == null ? "—" : `${n.toFixed(2)}s`);
// Minutes, as minutes. Never converted to a span — working time and elapsed
// span are different quantities (4B.20) and this one is working time.
const mins = (n) => (n == null ? "—" : `${Math.round(n).toLocaleString("en-US")} min`);

// How many trail rows the TABLE shows. The curve is never capped.
const TABLE_ROWS = 12;

/** First, last, and evenly-spaced middles. Never drops the two that matter. */
function sampleTrail(items, max) {
  if (items.length <= max) return items;
  const out = [items[0]];
  const step = (items.length - 1) / (max - 1);
  for (let n = 1; n < max - 1; n += 1) out.push(items[Math.round(n * step)]);
  out.push(items[items.length - 1]);
  return out;
}

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;      // never innerHTML for data
  return n;
}

// --- the money block ------------------------------------------------------
function renderMoney(m, portfolio) {
  const box = el("section", "sm-money");
  box.id = "sm-money";
  box.appendChild(el("h2", "sm-h", "What this plan costs"));
  if (!m) {
    box.appendChild(el("p", "sm-absent",
      "This document carries no cost ledger, so no total can be stated here."));
    return box;
  }
  const big = el("div", "sm-total");
  big.id = "sm-total";
  big.appendChild(el("span", "sm-total-num", money(m.total)));
  big.appendChild(el("span", "sm-total-lbl", "total ledger cost"));
  box.appendChild(big);

  const tbl = el("table", "sm-table");
  tbl.id = "sm-cost-table";
  const tb = el("tbody");
  for (const r of m.rows) {
    const tr = el("tr");
    tr.appendChild(el("td", "sm-k", r.label));
    tr.appendChild(el("td", "sm-v", money(r.value)));
    tr.dataset.source = r.source;
    tb.appendChild(tr);
  }
  // R-PD1 clause (4): the split decomposes tardiness rather than adding to it,
  // so it is indented under the tardiness row and never totalled beside it.
  if (m.split) {
    const f = el("tr", "sm-sub");
    f.appendChild(el("td", "sm-k", "…already late when the window opened"));
    f.appendChild(el("td", "sm-v", money(m.split.floor)));
    f.dataset.source = m.split.floorSource;
    const c = el("tr", "sm-sub");
    c.appendChild(el("td", "sm-k", "…added by this schedule"));
    c.appendChild(el("td", "sm-v", money(m.split.controllable)));
    c.dataset.source = m.split.controllableSource;
    tb.append(f, c);
  }
  tbl.appendChild(tb);
  box.appendChild(tbl);

  if (portfolio) box.appendChild(renderPortfolio(portfolio));
  return box;
}

// R-BK1: the published board is a portfolio, not a draw. Losing members'
// totals are PUBLISHED (clause 4) and a spread of one number is null, never
// 0.00 — so "not enough publishable members" is a state, not a zero.
function renderPortfolio(p) {
  const box = el("div", "sm-portfolio");
  box.id = "sm-portfolio";
  box.appendChild(el("div", "sm-sub-h", "How this plan was chosen"));
  if (p.declaration) box.appendChild(el("p", "sm-note", p.declaration));
  const tbl = el("table", "sm-table sm-members");
  tbl.id = "sm-portfolio-members";
  const tb = el("tbody");
  for (const mem of p.members) {
    const tr = el("tr", mem.seed === p.winnerSeed ? "sm-winner" : null);
    const k = el("td", "sm-k", `seed ${mem.seed}`);
    if (mem.seed === p.winnerSeed) k.appendChild(el("span", "sm-tag", "chosen"));
    tr.appendChild(k);
    tr.appendChild(el("td", "sm-v",
      mem.ledgerTotal == null ? (mem.reason || "not publishable")
                              : money(mem.ledgerTotal)));
    tb.appendChild(tr);
  }
  tbl.appendChild(tb);
  box.appendChild(tbl);
  box.appendChild(el("p", "sm-note", p.spreadPct == null
    ? "Fewer than two members finished with a comparable ledger, so no spread "
      + "between them can be stated."
    : `Spread between the publishable members: ${pct(p.spreadPct)} `
      + `(${money(p.spreadAbs)}).`));
  if (p.unpublished) box.appendChild(el("p", "sm-note", p.unpublished));
  return box;
}

// --- the solve-progress story (R-SP1) -------------------------------------
function renderProgress(pr) {
  const box = el("section", "sm-progress");
  box.id = "sm-progress";
  box.dataset.state = pr.state;
  box.appendChild(el("h2", "sm-h", "What the solver's search did"));

  // Clause (5): a board solved before the change has no trail and never will.
  // This is a permanent, honest state — not a spinner and not an error.
  if (pr.state === "absent" || pr.state === "none") {
    box.appendChild(el("p", "sm-absent", pr.sentence));
    return box;
  }

  const head = el("p", "sm-story");
  head.id = "sm-progress-story";
  head.textContent = pr.sentence;
  box.appendChild(head);

  // R-SP1 AMENDMENT 1 — THE DOLLAR PAIR, when both endpoints are ledger-priced.
  // The two figures are real costs of real solver-produced plans, so their
  // difference is ledger arithmetic end to end and currency is admissible. It
  // renders ABOVE the trail zone and outside it, because the zone below is the
  // scaled objective's and money may not enter it.
  if (pr.priced) {
    const pair = el("div", "sm-priced");
    pair.id = "sm-priced";
    const row = (lbl, v) => {
      const d = el("div", "sm-priced-row");
      d.appendChild(el("span", "sm-priced-lbl", lbl));
      d.appendChild(el("span", "sm-priced-num", money(v)));
      return d;
    };
    pair.append(row("the solver's first workable plan would have cost",
                    pr.firstPlanCost),
                row("the finished plan costs", pr.finalPlanCost));
    const saved = el("div", "sm-priced-row sm-priced-delta");
    saved.appendChild(el("span", "sm-priced-lbl",
      "the search took off its own first plan"));
    saved.appendChild(el("span", "sm-priced-num",
      `${money(pr.dollarImprovementAbs)}`
      + (pr.dollarImprovementPct == null ? ""
         : ` · ${pct(pr.dollarImprovementPct)}`)));
    pair.appendChild(saved);
    box.appendChild(pair);
  }

  // R-SP1 clause (2) and (3), VERBATIM from the server block. The cockpit does
  // not compose this wording; if these strings are ever empty the screen says
  // less, it never says more.
  const lbl2 = el("p", "sm-clause");
  lbl2.id = "sm-clause-2";
  lbl2.textContent = pr.clause2;
  const lbl3 = el("p", "sm-clause");
  lbl3.id = "sm-clause-3";
  lbl3.textContent = pr.clause3;
  box.append(lbl2, lbl3);

  // R-SP1 AMENDMENT 1's wall-cost disclosure. Capture costs wall time, and on a
  // wall-limited solve that is a fact about the plan the planner is looking at.
  // Empty (and absent) where it does not apply — under a deterministic budget
  // the search is unaffected and there is nothing to disclose.
  if (pr.captureNote) {
    const cn = el("p", "sm-note");
    cn.id = "sm-capture-note";
    cn.textContent = pr.captureNote;
    box.appendChild(cn);
  }

  // Clause (1): the trail belongs to ONE window and says so, because two
  // windows' trails are two solves of two problems and must never be summed.
  if (pr.windowKey) {
    const w = el("p", "sm-note");
    w.id = "sm-window-key";
    w.textContent = `This search is the window opening ${fmtFull(pr.windowKey)}`
      + ` · ${clockLabel()}. Each window is its own solve; their trails are `
      + `never added together.`;
    box.appendChild(w);
  }

  // THE SOLVER-UNITS ZONE (Session W2.2). Everything inside this container is
  // the SCALED OBJECTIVE's — the trail, the curve, the proof floor — and a
  // dollar sign may never enter it, in any state. It exists as a real container
  // because W2.2's predicate audit found W2.1's money guard ENUMERATING three
  // selectors while the section had grown four more; a zone can be asserted
  // whole, and a list has to be remembered.
  const zone = el("div", "sm-trail-zone");
  zone.id = "sm-trail-zone";

  if (pr.state === "present") {
    const shown = sampleTrail(pr.incumbents, TABLE_ROWS);
    const tbl = el("table", "sm-table sm-trail");
    tbl.id = "sm-trail";
    const th = el("thead");
    const hr = el("tr");
    hr.append(el("th", null, "plan"),
              el("th", null, `objective (${pr.unit})`),
              el("th", null, "solver elapsed"));
    th.appendChild(hr);
    const tb = el("tbody");
    shown.forEach((i, n) => {
      const tr = el("tr");
      tr.appendChild(el("td", "sm-k",
        n === 0 ? "first workable"
                : (n === shown.length - 1 ? "final" : `#${i.index}`)));
      tr.appendChild(el("td", "sm-v", units(i.objective)));
      // Clause (6): elapsed times are RECORDED facts that vary run to run. They
      // are shown because they are what the search actually took, and they are
      // never asserted by a test.
      tr.appendChild(el("td", "sm-v sm-dim", secs(i.elapsedS)));
      tb.appendChild(tr);
    });
    tbl.append(th, tb);
    zone.appendChild(tbl);
    // NO SILENT CAPS. A real board's search produces dozens to hundreds of
    // incumbents (46 on an eight-job specimen), and a table that quietly showed
    // twelve of them would read as "this is the whole search". The curve below
    // draws EVERY point; the table says what it left out and where the rest is.
    if (shown.length < pr.incumbents.length) {
      const note = el("p", "sm-note");
      note.id = "sm-trail-cap";
      note.textContent = `Showing ${shown.length} of ${pr.incumbents.length} `
        + `improvements, evenly sampled with the first and last kept. The curve `
        + `below plots all ${pr.incumbents.length}; the full trail is stored `
        + `with the run.`;
      zone.appendChild(note);
    }
    zone.appendChild(renderCurve(pr));
  }

  // Clause (4): the proof floor and the gap render WITH the story, in the gap
  // rider's own vocabulary.
  const proof = el("p", "sm-note");
  proof.id = "sm-proof-floor";
  proof.textContent = pr.gap == null
    ? `The solver reported no gap for this search, so the distance to the `
      + `cheapest plan is unknown.`
    : `Proof floor: the solver's own bound is ${units(pr.bestBound)} `
      + `${pr.unit}, leaving a gap of ${pct(pr.gap * 100)} — not proven `
      + `optimal; a cheaper plan may exist and could be up to that much `
      + `cheaper.`;
  zone.appendChild(proof);
  box.appendChild(zone);
  return box;
}

// A minimal inline-SVG curve. No dependency: it is a polyline over the trail.
function renderCurve(pr) {
  const pts = pr.incumbents.filter((i) => i.objective != null && i.elapsedS != null);
  const wrap = el("div", "sm-curve");
  wrap.id = "sm-curve";
  if (pts.length < 2) return wrap;
  const W = 420, H = 120, PAD = 8;
  const xs = pts.map((p) => p.elapsedS), ys = pts.map((p) => p.objective);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const y0 = Math.min(...ys), y1 = Math.max(...ys);
  const sx = (v) => PAD + (x1 === x0 ? 0 : (v - x0) / (x1 - x0)) * (W - 2 * PAD);
  const sy = (v) => H - PAD - (y1 === y0 ? 0 : (v - y0) / (y1 - y0)) * (H - 2 * PAD);
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label",
    "the solver's objective against its own elapsed time, first plan to last");
  const poly = document.createElementNS(NS, "polyline");
  poly.setAttribute("class", "sm-curve-line");
  poly.setAttribute("points", pts.map((p) => `${sx(p.elapsedS)},${sy(p.objective)}`).join(" "));
  svg.appendChild(poly);
  for (const p of pts) {
    const c = document.createElementNS(NS, "circle");
    c.setAttribute("class", "sm-curve-dot");
    c.setAttribute("cx", String(sx(p.elapsedS)));
    c.setAttribute("cy", String(sy(p.objective)));
    c.setAttribute("r", "2.5");
    svg.appendChild(c);
  }
  wrap.appendChild(svg);
  return wrap;
}

// --- the v1 statistics row ------------------------------------------------
function renderStats(s, util) {
  const box = el("section", "sm-stats");
  box.id = "sm-stats";
  box.appendChild(el("h2", "sm-h", "This plan in numbers"));
  const row = el("div", "sm-tiles");
  row.id = "sm-tiles";
  for (const st of s.stats) {
    const tile = el("div", "sm-tile");
    tile.dataset.source = st.source;
    tile.dataset.key = st.key;
    tile.appendChild(el("span", "sm-tile-num",
      st.kind === "money" ? money(st.value) : String(st.value)));
    tile.appendChild(el("span", "sm-tile-lbl", st.label));
    row.appendChild(tile);
  }
  box.appendChild(row);

  if (util) box.appendChild(renderUtilization(util));

  // THE HONEST GAP. Anything asked for that nothing stores is NAMED here rather
  // than computed client-side or quietly dropped. W2.2 landed the three rollups
  // W2.1 listed, so this is EMPTY today — and the block is skipped entirely
  // rather than rendered as an empty heading, because a heading with nothing
  // under it reads as a failure to load.
  if (s.gaps.length) {
    const gaps = el("div", "sm-gaps");
    gaps.id = "sm-gaps";
    gaps.appendChild(el("div", "sm-sub-h", "Asked for, and not shown"));
    const ul = el("ul", "sm-gaplist");
    for (const g of s.gaps) {
      const li = el("li");
      li.dataset.key = g.key;
      li.appendChild(el("strong", null, g.label));
      li.appendChild(document.createTextNode(` — ${g.why}. Should come from ${g.from}.`));
      ul.appendChild(li);
    }
    gaps.append(ul);
    box.appendChild(gaps);
  }
  return box;
}

// W2.2 B2 — UTILIZATION BY MACHINE, WITH ITS DENOMINATOR.
//
// A list rather than a tile, because a ratio needs somewhere to put the two
// numbers it came from. Every row shows worked and open minutes beside the
// percentage, and the block prints the SERVER's definition string — the cockpit
// never words it, so it cannot re-imply a denominator of its own (4B.20).
function renderUtilization(u) {
  const box = el("div", "sm-util");
  box.id = "sm-util";
  box.dataset.source = u.source;
  box.appendChild(el("div", "sm-sub-h", "Utilization by machine"));
  const tbl = el("table", "sm-table");
  tbl.id = "sm-util-table";
  const th = el("thead");
  const hr = el("tr");
  hr.append(el("th", null, "machine"), el("th", null, "worked"),
            el("th", null, "open"), el("th", null, "utilization"));
  th.appendChild(hr);
  const tb = el("tbody");
  for (const r of u.rows) {
    const tr = el("tr");
    tr.dataset.resource = r.resourceId;
    tr.appendChild(el("td", "sm-k", r.name));
    tr.appendChild(el("td", "sm-v sm-dim", mins(r.workingMinutes)));
    tr.appendChild(el("td", "sm-v sm-dim", mins(r.openCapacityMinutes)));
    // A machine with no denominator keeps its row and says there is no ratio —
    // dropping it would make the list read as "every machine we could measure".
    tr.appendChild(el("td", "sm-v", r.utilization == null
      ? "no open capacity recorded"
      : pct(r.utilization * 100)));
    tb.appendChild(tr);
  }
  tbl.append(th, tb);
  box.appendChild(tbl);
  if (u.definition) {
    const d = el("p", "sm-note");
    d.id = "sm-util-definition";
    d.textContent = `Utilization here is ${u.definition}. The board's own `
      + `per-row figure is computed over the window you are looking at, so the `
      + `two answer different questions and may differ.`;
    box.appendChild(d);
  }
  return box;
}

/**
 * Build the summary screen for a document. Returns the element; the caller
 * mounts it. Pure with respect to the document — it reads nothing else.
 */
export function buildSummary(doc) {
  const m = summaryModel(doc);
  const root = el("div", "summary");
  root.id = "summary-screen";
  const head = el("header", "sm-head");
  head.appendChild(el("h1", "sm-title", "Plan summary"));
  if (m.scheduleId) {
    head.appendChild(el("code", "sm-id", m.scheduleId));
  }
  head.appendChild(el("span", "sm-ro", "read-only · post-solve"));
  root.appendChild(head);
  root.appendChild(renderMoney(m.money, m.portfolio));
  root.appendChild(renderProgress(m.progress));
  root.appendChild(renderStats(m.stats, m.utilization));
  return root;
}

/** Mount the screen as an overlay panel over the cockpit, with a close. */
export function mountSummary(doc, { onClose } = {}) {
  const prev = document.getElementById("summary-overlay");
  if (prev) prev.remove();
  const overlay = el("div", "summary-overlay");
  overlay.id = "summary-overlay";
  const panel = buildSummary(doc);
  const close = el("button", "sm-close", "close");
  close.id = "sm-close";
  close.addEventListener("click", () => {
    overlay.remove();
    if (onClose) onClose();
  });
  panel.querySelector(".sm-head").appendChild(close);
  overlay.appendChild(panel);
  document.body.appendChild(overlay);
  return overlay;
}
