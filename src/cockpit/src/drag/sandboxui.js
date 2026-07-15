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

export function createDeltaCard(hostEl, { onDiscard, onNavigate, onAccept, onPublish }) {
  const card = document.createElement("div");
  card.className = "delta-card hidden";
  hostEl.appendChild(card);
  let countdownTimer = null;

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

  // VERDICT / FLAGGED / RETURN-HOME. `nameOf(rid)` and `woOf(opRef)` resolve
  // planner vocabulary for the line items. Returns the card element.
  function showResult(result, { nameOf, woOf }) {
    _stopCountdown();
    const outcome = result.outcome;
    const returnHome = outcome === "no_verdict" || !result.feasible;
    card.className = `delta-card ${returnHome ? "return-home" : outcome}`;

    const headline = returnHome
      ? "Returned home"
      : _deltaHeadline(result);
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
      // the "why" clause (session 3.3 CU3): each major consequence names its
      // reason, sourced from the re-solve's own occupancy arithmetic.
      const why = _reasonClause(m.reason, { nameOf, woOf });
      return `<button class="dc-line${m.pinned ? " pinned" : ""}" data-op="${m.operation_ref}">
        <span class="dc-wo">${wo}</span><span class="dc-move">${move}${shift}</span>
        ${m.pinned ? '<span class="dc-pin">dropped</span>' : ""}
        ${why ? `<span class="dc-why">${why}</span>` : ""}</button>`;
    }).join("");
    // CU4: a ghost drop traces the dropped bar instantly, then fills in the full
    // moved-set from the vouching schedule — say so while it loads (R-DP7).
    const pending = !returnHome && result.consequences_pending
      ? `<div class="dc-note pending">consequences loading…</div>` : "";

    card.innerHTML = `
      <div class="dc-head">
        <span class="dc-outcome ${outcome}">${headline}</span>
        <span class="dc-status">${status}</span>
      </div>
      ${returnHome ? `<div class="dc-reason">${result.message || "couldn't verify this placement"}</div>` : ""}
      ${lineHtml ? `<div class="dc-lines">${lineHtml}</div>` : ""}
      ${pending}
      <div class="dc-actions">
        ${returnHome ? "" : `<button class="dc-accept">Accept</button>`}
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
    for (const b of card.querySelectorAll(".dc-line")) {
      b.addEventListener("click", () => onNavigate && onNavigate(b.dataset.op));
    }
    return card;
  }

  // ACCEPTED: the edit is now a NEW proposed version (the base stands untouched).
  // Publish is the explicit second act. Keeps the moved-set line items on screen
  // so the accepted change stays legible until published or discarded (R-DP7).
  function showAccepted({ newScheduleId, decision }) {
    _stopCountdown();
    card.className = "delta-card accepted";
    const delta = decision && decision.delta_abs != null
      ? ` · ${decision.delta_abs >= 0 ? "+" : "−"}$${Math.abs(decision.delta_abs).toLocaleString()}`
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

  function _deltaHeadline(result) {
    const d = result.delta_pct;
    if (d == null) return "Feasible";
    if (Math.abs(d) < 1e-6) return "Same cost";
    const abs = result.delta_abs != null ? ` · ${result.delta_abs > 0 ? "+" : "−"}$${Math.abs(result.delta_abs).toLocaleString()}` : "";
    return `${d > 0 ? "+" : "−"}${Math.abs(d).toFixed(2)}% cost${abs}`;
  }

  return { showPending, showResult, showAccepted, showPublished, hide, el: card };
}
