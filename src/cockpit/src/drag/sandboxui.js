// The sandbox delta card (CU4, R-T1c / R-DP7). A dropped bar's lifecycle after
// it lands as a tentative:
//   * PENDING  — a visible countdown against the budget token while the Tier-2
//     re-solve runs; the board is never blocked (the card floats, the board
//     stays live).
//   * VERDICT  — the delta card: headline cost delta + the moved-set as line
//     items, each linked to its board trace (click a line → navigate to the
//     bar, R-DP7c).
//   * FLAGGED  — "≈ delta, bound not proven" (SOLVER_NONOPTIMAL surfaced): a
//     shippable card wearing an honesty flag (outcome 2).
//   * RETURN-HOME — no verdict / infeasible: the bar goes home animated with
//     the reason (outcome 3, R-DP2); no card line items.
//
// Accept is REAL now (CU1, R-DP7): accepting mints a new proposed schedule
// version (the base is never mutated) and rebinds the board; publish is the
// explicit second act (proposed → published). The card walks
// verdict → accepted → published, each step honest about what happened. Discard
// restores everything at any pre-publish step (the controller animates it).

export function createDeltaCard(hostEl, { onDiscard, onNavigate, onAccept, onPublish, onAskWhy }) {
  const card = document.createElement("div");
  card.className = "delta-card hidden";
  hostEl.appendChild(card);
  let countdownTimer = null;

  // BEAT ONE (R-T2): the feasibility ghost's NON-MONETARY state. R-T2(1): no
  // figure, no delta — only "possible, pricing it now". The board draws the
  // placement in the R-M1 ghost class; this card slot reads the same register.
  function showPricing(feasibilityBudgetS = 2.0, tickMs = 100) {
    _stopCountdown();
    card.className = "delta-card pricing";
    card.innerHTML = `
      <div class="dc-head"><span class="dc-outcome pricing">checking feasibility…</span>
        <span class="dc-status">beat 1 · placement only, no price yet</span></div>
      <div class="dc-countdown"><div class="dc-countdown-fill" style="width:100%"></div></div>
      <div class="dc-note">this is possible here — pricing it now</div>`;
    const fill = card.querySelector(".dc-countdown-fill");
    const t0 = performance.now();
    countdownTimer = setInterval(() => {
      const frac = Math.max(0, 1 - (performance.now() - t0) / (feasibilityBudgetS * 1000));
      fill.style.width = `${(frac * 100).toFixed(1)}%`;
      if (frac <= 0) _stopCountdown();
    }, tickMs);
  }

  function hide() {
    _stopCountdown();
    card.className = "delta-card hidden";
    card.replaceChildren();
  }

  function _stopCountdown() {
    if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
  }

  // PENDING: the countdown. `budgetS` paces the bar; the real wait is the
  // server's (this only animates the token). `tickMs` from feel.
  function showPending(budgetS, tickMs = 100) {
    _stopCountdown();
    card.className = "delta-card pending";
    card.innerHTML = `
      <div class="dc-head"><span class="dc-outcome pending">re-solving…</span>
        <span class="dc-status">Tier-2 sandbox · budget ${budgetS}s</span></div>
      <div class="dc-countdown"><div class="dc-countdown-fill" style="width:100%"></div></div>
      <div class="dc-note">the board stays live — this never blocks it</div>`;
    const fill = card.querySelector(".dc-countdown-fill");
    const t0 = performance.now();
    countdownTimer = setInterval(() => {
      const frac = Math.max(0, 1 - (performance.now() - t0) / (budgetS * 1000));
      fill.style.width = `${(frac * 100).toFixed(1)}%`;
      if (frac <= 0) _stopCountdown();
    }, tickMs);
  }

  // VERDICT / FLAGGED / RETURN-HOME — BEAT TWO, the LAYERED priced card (R-T2
  // CU2). `nameOf(rid)`/`woOf(opRef)` resolve planner vocabulary; `opts.detailOpen`
  // (a feel token) sets the detail layer's default expansion; `opts.superseded`
  // (R-T2(3)) plays the ghost→card transition. Returns the card element.
  //
  // ALWAYS-VISIBLE layer (decision-sufficient ON ITS OWN): signed total + verdict,
  // the moved op's final placement, top-N affected orders with per-order deltas,
  // lateness introduced/recovered, the dominant driver (hedged), and the standing
  // "no committed work changes" line. DETAIL layer (same card, a disclosure): the
  // cost decomposition by ledger line + the full operational consequences.
  function showResult(result, { nameOf, woOf } = {}, opts = {}) {
    _stopCountdown();
    const outcome = result.outcome;
    const returnHome = outcome === "no_verdict" || !result.feasible;
    card.className = `delta-card ${returnHome ? "return-home" : outcome}`
      + (opts.superseded ? " superseded" : "");

    const headline = returnHome ? "Returned home" : _deltaHeadline(result);
    const status = {
      verdict: "verdict · proven within budget",
      feasible_unproven: "flagged · bound not proven",
      no_verdict: "no verdict · returned home",
    }[outcome] || outcome;

    const lines = returnHome ? [] : (result.moves || []);
    const lineHtml = lines.map((m) => {
      const wo = woOf(m.operation_ref) || m.operation_ref.slice(0, 8);
      const from = nameOf(m.from_resource), to = nameOf(m.to_resource);
      const move = m.resource_changed ? `${from} → ${to}` : `${to}`;
      const shift = m.start_delta_min ? ` · ${m.start_delta_min > 0 ? "+" : ""}${m.start_delta_min}min` : "";
      const why = _reasonClause(m.reason, { nameOf, woOf });
      return `<button class="dc-line${m.pinned ? " pinned" : ""}" data-op="${m.operation_ref}">
        <span class="dc-wo">${wo}</span><span class="dc-move">${move}${shift}</span>
        ${m.pinned ? '<span class="dc-pin">dropped</span>' : ""}
        ${why ? `<span class="dc-why">${why}</span>` : ""}</button>`;
    }).join("");
    const pending = !returnHome && result.consequences_pending
      ? `<div class="dc-note pending">consequences loading…</div>` : "";
    const equivalent = !returnHome && !result.consequences_pending && lines.length === 0
      ? `<div class="dc-note">equivalent placement — nothing else moved</div>` : "";

    // --- always-visible extras (CU2) ------------------------------------
    const alwaysVisible = returnHome ? "" : [
      _placementLine(result, { nameOf, woOf }),
      _latenessLine(result),
      _affectedOrdersHtml(result),
      _driverLine(result),
      // the standing invariant, always shown (a true guarantee, stated plainly)
      result.no_committed_work_changes !== false
        ? `<div class="dc-note committed-safe">no committed work changes</div>` : "",
    ].filter(Boolean).join("");

    // --- detail layer (CU2): cost decomposition + operational consequences ---
    const detail = returnHome ? "" : _detailLayer(result, lineHtml, equivalent, pending,
      { open: !!opts.detailOpen });

    card.innerHTML = `
      <div class="dc-head">
        <span class="dc-outcome ${outcome}">${headline}</span>
        <span class="dc-status">${status}</span>
      </div>
      ${returnHome ? `<div class="dc-reason">${result.message || "couldn't verify this placement"}</div>` : ""}
      ${alwaysVisible}
      ${detail}
      <div class="dc-actions">
        ${returnHome ? "" : `<button class="dc-accept">Accept</button>`}
        ${returnHome ? "" : `<button class="dc-askwhy">Ask why</button>`}
        <button class="dc-discard">Discard</button>
      </div>`;

    card.querySelector(".dc-discard").addEventListener("click", () => onDiscard && onDiscard());
    const acceptBtn = card.querySelector(".dc-accept");
    if (acceptBtn) {
      acceptBtn.addEventListener("click", () => {
        acceptBtn.disabled = true;
        acceptBtn.textContent = "accepting…";
        onAccept && onAccept();
      });
    }
    const askBtn = card.querySelector(".dc-askwhy");
    if (askBtn) askBtn.addEventListener("click", () => onAskWhy && onAskWhy(result));
    for (const b of card.querySelectorAll(".dc-line")) {
      b.addEventListener("click", () => onNavigate && onNavigate(b.dataset.op));
    }
    // R-T2(3): a perceivable ghost→card transition. Retrigger the class.
    if (opts.superseded) { void card.offsetWidth; card.classList.add("superseded"); }
    return card;
  }

  // The moved op's FINAL placement (always-visible): where the dropped bar landed.
  function _placementLine(result, { nameOf, woOf }) {
    const pin = (result.moves || []).find((m) => m.pinned) || null;
    const rid = pin ? pin.to_resource : (result.pin && result.pin.resource_id);
    const opRef = pin ? pin.operation_ref : (result.pin && result.pin.operation_ref);
    if (!rid) return "";
    const wo = (woOf && woOf(opRef)) || (opRef || "").slice(0, 8) || "the op";
    const when = pin ? _shortDate(pin.to_start) : _shortDate(result.pin && result.pin.start);
    return `<div class="dc-placement"><b>${wo}</b> → ${(nameOf && nameOf(rid)) || rid}${when ? ` · ${when}` : ""}</div>`;
  }

  // Lateness introduced (+) or recovered (−), as one plain statement.
  function _latenessLine(result) {
    const d = result.lateness_delta_min;
    if (d == null || d === 0) return `<div class="dc-lateness on-time">no change to lateness</div>`;
    const hrs = (Math.abs(d) / 60).toFixed(1);
    return d > 0
      ? `<div class="dc-lateness worse">introduces ${hrs}h of lateness</div>`
      : `<div class="dc-lateness better">recovers ${hrs}h of lateness</div>`;
  }

  // Top-N affected orders, each with its own tardiness ($) + lateness (min)
  // delta. CU5a (4B.3c): this column is the per-Demand LATENESS/TARDINESS impact
  // ONLY — the ledger does not roll PRODUCTION dollars per order (a named debt), so
  // the header must never read "cost impact". The tardiness dollars shown are the
  // per-Demand tardiness penalty, part of the whole-plan cost decomposition below.
  function _affectedOrdersHtml(result) {
    const orders = result.affected_orders || [];
    if (!orders.length) return "";
    const rows = orders.map((o) => {
      const wo = o.work_order || (o.demand_ref || "").slice(0, 8);
      const t = o.tardiness_delta;
      const tstr = (t != null && Math.abs(t) >= 0.005)
        ? `${t > 0 ? "+" : "−"}$${Math.abs(t).toLocaleString(undefined, { maximumFractionDigits: 2 })}` : "";
      const l = o.lateness_delta_min;
      const lstr = (l != null && l !== 0)
        ? `${l > 0 ? "+" : "−"}${Math.abs(l)}min` : "";
      return `<div class="dc-order"><span class="dc-wo">${wo}</span>
        <span class="dc-order-delta">${[tstr, lstr].filter(Boolean).join(" · ") || "no lateness change"}</span></div>`;
    }).join("");
    return `<div class="dc-orders"><div class="dc-orders-h">affected orders — lateness / tardiness impact</div>${rows}</div>`;
  }

  // The dominant driver in plain language, HEDGED where the attribution is by
  // price rank alone (docs/02 §4.2 — EARLINESS_PREFERENCE).
  function _driverLine(result) {
    const d = result.dominant_driver;
    if (!d || !d.phrase) return "";
    const hedge = d.hedge ? ` ${d.hedge}` : "";
    return `<div class="dc-driver">why: ${d.phrase}${hedge}</div>`;
  }

  // The DETAIL layer as a native disclosure — cost decomposition by ledger line
  // (summing to the verdict) + the operational consequences (the moved-set).
  function _detailLayer(result, lineHtml, equivalent, pending, { open }) {
    const lines = result.cost_lines || [];
    const decompHtml = lines.length ? lines.map((l) => {
      const v = l.delta;
      const vstr = Math.abs(v) < 0.005 ? "$0"
        : `${v > 0 ? "+" : "−"}$${Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
      return `<div class="dc-costline"><span>${l.line}</span><span>${vstr}</span></div>`;
    }).join("") : "";
    const decomp = decompHtml
      ? `<div class="dc-decomp"><div class="dc-decomp-h">cost by line</div>${decompHtml}</div>` : "";
    const consequences = lineHtml
      ? `<div class="dc-lines">${lineHtml}</div>` : (equivalent || pending);
    if (!decomp && !consequences) return "";
    return `<details class="dc-detail-layer"${open ? " open" : ""}>
      <summary>details — cost by line, operational consequences</summary>
      ${decomp}${consequences}</details>`;
  }

  // ACCEPTED: the edit is now a NEW proposed version (the base stands untouched).
  // Publish is the explicit second act. Keeps the moved-set line items on screen
  // so the accepted change stays legible until published or discarded (R-DP7).
  function showAccepted({ newScheduleId, decision }) {
    _stopCountdown();
    card.className = "delta-card accepted";
    // LEDGER dollars only (exit-audit fix): cost_delta.total_delta is the true
    // decomposed cost delta; decision.delta_abs is the SCALED objective and is
    // never shown as dollars.
    const td = decision && decision.cost_delta && decision.cost_delta.total_delta;
    const delta = td != null
      ? ` · ${td >= 0 ? "+" : "−"}$${Math.abs(td).toLocaleString(undefined, { maximumFractionDigits: 2 })}`
      : "";
    const shortId = (newScheduleId || "").slice(0, 8);
    card.innerHTML = `
      <div class="dc-head">
        <span class="dc-outcome accepted">Accepted${delta}</span>
        <span class="dc-status">new version <b>${shortId}</b> · proposed</span>
      </div>
      <div class="dc-reason">the base is untouched — publish to make this the schedule of record</div>
      <div class="dc-actions">
        <button class="dc-publish">Publish</button>
        <button class="dc-discard">Discard</button>
      </div>`;
    card.querySelector(".dc-discard").addEventListener("click", () => onDiscard && onDiscard());
    const pub = card.querySelector(".dc-publish");
    pub.addEventListener("click", () => {
      pub.disabled = true; pub.textContent = "publishing…";
      onPublish && onPublish();
    });
    return card;
  }

  // PUBLISHED: proposed → published; the prior version is superseded. Terminal.
  function showPublished({ scheduleId, superseded }) {
    _stopCountdown();
    card.className = "delta-card published";
    const supN = (superseded || []).length;
    card.innerHTML = `
      <div class="dc-head">
        <span class="dc-outcome published">Published ✓</span>
        <span class="dc-status">${(scheduleId || "").slice(0, 8)} is the schedule of record</span>
      </div>
      <div class="dc-reason">${supN ? `the prior version was superseded` : "now the schedule of record"}</div>
      <div class="dc-actions"><button class="dc-discard">Close</button></div>`;
    card.querySelector(".dc-discard").addEventListener("click", () => onDiscard && onDiscard());
    return card;
  }

  // REFUSED (session 4.0c, R-M1a): an accept the server would not commit (a 409
  // that is NOT "superseded" — e.g. an infeasible pin, an R-DP1 violation, or a
  // storage failure). Pre-4.0c this returned the bar home with the card hidden
  // and no reason — a committed-looking edit vanishing silently. The refusal is
  // now LOUD: an authored line saying nothing changed, the raw server reason kept
  // as a muted detail (never hidden), and the card shakes (R-M1a). The bar still
  // snaps home as a rejection — the controller drives that; the card stays.
  function showRefused({ reason } = {}) {
    _stopCountdown();
    card.className = "delta-card refused";
    card.innerHTML = `
      <div class="dc-head">
        <span class="dc-outcome refused">Edit not saved</span>
        <span class="dc-status">the plan is unchanged</span>
      </div>
      <div class="dc-reason">This placement couldn't be committed — the schedule of
        record still stands. Nothing was changed.</div>
      ${reason ? `<div class="dc-detail"></div>` : ""}
      <div class="dc-actions"><button class="dc-discard">Close</button></div>`;
    if (reason) card.querySelector(".dc-detail").textContent = String(reason);
    card.querySelector(".dc-discard").addEventListener("click", () => onDiscard && onDiscard());
    // Retrigger the shake if the class was already present (re-refusal).
    void card.offsetWidth;
    return card;
  }

  // Render the structured move reason (session 3.3 CU3) into a planner-facing
  // one-clause "why". The backend emits ids only (occupancy: which machine, and
  // until when; or the dropped op displaced it); the card resolves names here.
  function _reasonClause(reason, { nameOf, woOf }) {
    if (!reason) return "";
    if (reason.kind === "displaced_by_drop") return "displaced by the dropped op";
    if (reason.kind === "occupancy") {
      const machine = nameOf(reason.on_resource) || "the machine";
      const until = _shortDate(reason.until);
      return `blocked on ${machine}${until ? ` until ${until}` : ""}`;
    }
    return "";
  }

  function _shortDate(iso) {
    const t = Date.parse(iso);
    if (Number.isNaN(t)) return "";
    return new Date(t).toLocaleString(undefined,
      { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  }

  // The headline shows LEDGER dollars only (exit-audit fix): `cost_delta_abs`
  // (+ `cost_delta_pct`) is the true dollar delta from the re-solve's ledger.
  // `delta_abs`/`delta_pct` are the SCALED solver objective (~100× dollars,
  // tardiness-weighted) — NEVER shown as a dollar amount. When no ledger dollar
  // figure is available (a pool-ghost drop, a fixture), the card degrades to a
  // relative-% label ("vs current plan") — an honest signal, never a false $.
  function _deltaHeadline(result) {
    const cAbs = result.cost_delta_abs, cPct = result.cost_delta_pct;
    if (cAbs != null) {
      if (Math.abs(cAbs) < 0.005) return "Same cost";
      const pct = cPct != null ? `${cPct > 0 ? "+" : "−"}${Math.abs(cPct).toFixed(2)}% cost · ` : "";
      return `${pct}${cAbs > 0 ? "+" : "−"}$${Math.abs(cAbs).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
    }
    // no ledger dollars → relative objective change only, labelled honestly
    const d = result.delta_pct;
    if (d == null) return "Feasible";
    if (Math.abs(d) < 1e-6) return "Same plan";
    return `${d > 0 ? "+" : "−"}${Math.abs(d).toFixed(2)}% vs current plan`;
  }

  return { showPending, showPricing, showResult, showAccepted, showPublished,
           showRefused, hide, el: card };
}
