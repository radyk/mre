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
// Accept is STUBBED DISABLED this session — the publish workflow isn't built,
// and a dead-end accept would violate R-DP7's no-silent-change law. Discard is
// the only commit verb; it restores everything (the controller animates it).

export function createDeltaCard(hostEl, { onDiscard, onNavigate }) {
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
      return `<button class="dc-line${m.pinned ? " pinned" : ""}" data-op="${m.operation_ref}">
        <span class="dc-wo">${wo}</span><span class="dc-move">${move}${shift}</span>
        ${m.pinned ? '<span class="dc-pin">dropped</span>' : ""}</button>`;
    }).join("");

    card.innerHTML = `
      <div class="dc-head">
        <span class="dc-outcome ${outcome}">${headline}</span>
        <span class="dc-status">${status}</span>
      </div>
      ${returnHome ? `<div class="dc-reason">${result.message || "couldn't verify this placement"}</div>` : ""}
      ${lineHtml ? `<div class="dc-lines">${lineHtml}</div>` : ""}
      <div class="dc-actions">
        <button class="dc-accept" disabled title="Publish workflow arrives in the next build.">Accept</button>
        <button class="dc-discard">Discard</button>
      </div>`;

    card.querySelector(".dc-discard").addEventListener("click", () => onDiscard && onDiscard());
    for (const b of card.querySelectorAll(".dc-line")) {
      b.addEventListener("click", () => onNavigate && onNavigate(b.dataset.op));
    }
    return card;
  }

  function _deltaHeadline(result) {
    const d = result.delta_pct;
    if (d == null) return "Feasible";
    if (Math.abs(d) < 1e-6) return "Same cost";
    const abs = result.delta_abs != null ? ` · ${result.delta_abs > 0 ? "+" : "−"}$${Math.abs(result.delta_abs).toLocaleString()}` : "";
    return `${d > 0 ? "+" : "−"}${Math.abs(d).toFixed(2)}% cost${abs}`;
  }

  return { showPending, showResult, hide, el: card };
}
