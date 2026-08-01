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

// The authored line the card shows when the total could NOT be split — the exact
// wording `mre.modules.sandbox.UNSPLIT_NOTE` carries (one sentence, two
// languages; a `test_delta_attribution` counterpart pins the Python side).
export const UNSPLIT_NOTE = "includes window re-optimization";

// "+$1,234.56" / "−$375.83" / "$0" — ONE money formatter, so the split block, the
// decomposition and the headline can never disagree about how a signed dollar
// figure reads. Below half a cent is "$0": a sign on a rounding residue is noise
// dressed as information.
export function signedMoney(v) {
  if (v == null) return "";
  if (Math.abs(v) < 0.005) return "$0";
  const abs = Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 2 });
  return `${v > 0 ? "+" : "−"}$${abs}`;
}

// The card's ATTRIBUTION rows (CU1, Session 4B.5) — a PURE read of the beat-two
// payload, unit-tested framework-free in the `logic` harness project.
//
// Returns the two split rows when the baseline was proven, and null when it was
// not (the caller then renders the unsplit note). Never a partial split: an
// attribution with one part missing is not an attribution.
export function attributionRows(result) {
  if (!result) return null;
  // Session 4B.24 (R-T2 amendment clause 2): a LOCALLY priced move has ONE row.
  // There is no window-re-optimization component to show — not "we measured it
  // and it was zero", but "nothing else was allowed to move, so there is nothing
  // else in this number". Rendering a `window re-optimization $0` line would
  // claim a measurement nobody took.
  if (result.attribution === "local") {
    if (result.move_delta_abs == null) return null;
    return [{ key: "your move", value: result.move_delta_abs, own: true }];
  }
  if (result.attribution !== "split") return null;
  if (result.reopt_delta_abs == null || result.move_delta_abs == null) return null;
  return [
    { key: "window re-optimization", value: result.reopt_delta_abs, own: false },
    { key: "your move", value: result.move_delta_abs, own: true },
  ];
}

// The one sentence that makes a locally priced number readable: it says what was
// held, so "your move" can be read as literally the move.
export const LOCAL_NOTE =
  "everything else held where it is — this is the move and nothing else";

// The OPPORTUNITY section (clause 3). The search's discovery about the window is
// never the planner's move, so it renders in its own block with its own delta,
// its own affected list and its own accept. Pure: returns null when there is
// nothing to offer, so a card can never grow an empty heading.
export function opportunityBlock(result) {
  const o = result && result.opportunity;
  if (!o || !o.found || o.delta_abs == null) return null;
  return {
    delta_abs: o.delta_abs,
    sentence: o.sentence || "",
    affected: o.affected_orders || [],
    movedOps: o.moved_op_count || 0,
  };
}

// R-BK1 clause (4) — THE LOSING MEMBERS ARE NOT DISCARDED SILENTLY.
//
// The JS DECIDES whether there is a portfolio line and never WORDS it: the
// three registers (all landed on the same total / within X% / spread X% apart —
// far from settled) are authored in `portfolio.agreement_sentence` so the card
// and any other surface cannot state different things about one search. Returns
// null at K=1, where there is no portfolio and nothing to say about a spread —
// a card must never grow an empty heading (the 4B.24 rule, one block over).
export function portfolioLine(result) {
  const p = result && result.portfolio;
  if (!p || !(p.k > 1)) return null;
  const parts = [p.declaration, p.agreement, p.unpublished].filter((s) => s);
  if (!parts.length) return null;
  return { k: p.k, text: parts.join(" — ") };
}

export function createDeltaCard(hostEl, { onDiscard, onNavigate, onAccept, onPublish, onAskWhy, onRetry, onSearchDeeper, onAcceptSearch }) {
  const card = document.createElement("div");
  card.className = "delta-card hidden";
  hostEl.appendChild(card);
  let countdownTimer = null;

  // BEAT ONE (R-T2): the feasibility ghost's NON-MONETARY state. R-T2(1): no
  // figure, no delta. The board draws the placement in the R-M1 ghost class;
  // this card slot reads the same register.
  //
  // Session 4B.23: the note used to read "this is possible here — pricing it
  // now" while the check was STILL RUNNING. It is rendered before the request is
  // sent, so on every drop it asserted an answer nobody had yet — and on the
  // dense board the answer that arrived four seconds later was the opposite. A
  // pending state may describe what we are DOING and nothing else.
  function showPricing(feasibilityBudgetS = 2.0, tickMs = 100) {
    _stopCountdown();
    card.className = "delta-card pricing";
    card.innerHTML = `
      <div class="dc-head"><span class="dc-outcome pricing">checking feasibility…</span>
        <span class="dc-status">beat 1 · placement only, no price yet</span></div>
      <div class="dc-countdown"><div class="dc-countdown-fill" style="width:100%"></div></div>
      <div class="dc-note">seeing whether this can go here at all</div>`;
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

  // --- Session 4B.23: A REFUSAL AND A FAILURE ARE DIFFERENT THINGS ---------
  //
  // Before this session the only exit from a beat that did not produce a card
  // was a SILENT SNAP-BACK — `returnHome` with the card hidden. One animation
  // stood for a refusal, a timeout, a crash, a dropped connection and a closed
  // calendar, so the founder watched his own product and concluded it was
  // broken. Both states below keep the card on screen; neither may be silent.
  //
  // IMPOSSIBLE is a PRODUCT ANSWER: we asked the plant and the plant said no.
  // It is stated in the plant's voice, it names the reason, and it does not
  // apologise — there is nothing to be sorry about and nothing to retry.
  function showImpossible({ reason, beat } = {}) {
    _stopCountdown();
    card.className = "delta-card impossible";
    card.innerHTML = `
      <div class="dc-head">
        <span class="dc-outcome impossible">Can't go here</span>
        <span class="dc-status">${beat === "one" ? "beat 1 · proven" : "proven"}</span>
      </div>
      <div class="dc-reason"></div>
      <div class="dc-note">the bar is back where it was — nothing changed.</div>
      <div class="dc-actions"><button class="dc-discard">Close</button></div>`;
    card.querySelector(".dc-reason").textContent =
      String(reason || "this placement isn't possible here");
    card.querySelector(".dc-discard").addEventListener("click", () => onDiscard && onDiscard());
    return card;
  }

  // FAILURE is an APOLOGY: WE could not finish, so the plant said nothing and
  // nothing may be claimed on its behalf. It names WHICH BEAT failed and offers
  // a retry. The `what` is an AUTHORED sentence — the raw transport string never
  // reaches this surface (a bare "Failed to fetch" has previously landed in
  // front of a planner), and lives on `drag.state().failure` for debugging.
  function showFailure({ beat, what } = {}) {
    _stopCountdown();
    card.className = "delta-card failure";
    const which = beat === "one" ? "feasibility check" : "pricing re-solve";
    card.innerHTML = `
      <div class="dc-head">
        <span class="dc-outcome failure">Couldn't price this</span>
        <span class="dc-status">beat ${beat === "one" ? "1" : "2"} · ${which} failed</span>
      </div>
      <div class="dc-reason">I couldn't run the ${which}, so I don't know what this
        move would cost. This is not a verdict about the placement — the plan is
        unchanged and the bar is back where it was.</div>
      <div class="dc-detail-cause"></div>
      <div class="dc-actions">
        <button class="dc-retry">Try again</button>
        <button class="dc-discard">Close</button>
      </div>`;
    card.querySelector(".dc-detail-cause").textContent =
      String(what || "it could not be completed");
    card.querySelector(".dc-discard").addEventListener("click", () => onDiscard && onDiscard());
    card.querySelector(".dc-retry").addEventListener("click", () => onRetry && onRetry());
    return card;
  }

  // PENDING: the countdown. `budgetS` paces the bar; the real wait is the
  // server's (this only animates the token). `tickMs` from feel.
  //
  // `note.beatOne` (Session 4B.23) carries what beat one managed to say, because
  // arriving at beat two is no longer proof that beat one succeeded:
  //   "undetermined" — the feasibility check ran out of ITS budget. Pricing goes
  //                    ahead; beat two is the authority. Never rendered as
  //                    "impossible", which is a claim about the plant.
  //   "failed"       — beat one could not be completed at all. Same: pricing
  //                    proceeds, and the planner is told, rather than watching a
  //                    silent extra wait.
  function showPending(budgetS, tickMs = 100, note = {}) {
    _stopCountdown();
    card.className = "delta-card pending";
    const beatOne = note.beatOne;
    const caveat =
      beatOne === "undetermined"
        ? `<div class="dc-note beat-one-note undetermined">the quick check ran out of
             time before it could tell — that's my budget, not a verdict. Pricing
             it properly now; this beat is the one that decides.</div>`
      : beatOne === "failed"
        ? `<div class="dc-note beat-one-note failed">the quick feasibility check
             didn't answer — ${(note.beatOneError && note.beatOneError.what)
               || "it could not be completed"}. Pricing it anyway; this beat is
             the one that decides.</div>`
        : "";
    card.innerHTML = `
      <div class="dc-head"><span class="dc-outcome pending">re-solving…</span>
        <span class="dc-status">Tier-2 sandbox · budget ${budgetS}s</span></div>
      <div class="dc-countdown"><div class="dc-countdown-fill" style="width:100%"></div></div>
      ${caveat}
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

    // Session 4B.23: "Returned home" was ONE headline over two different things.
    // `no_verdict` means the re-solve ran out of OUR budget — an apology, and
    // NOT a statement that the placement is impossible; a proven-INFEASIBLE
    // verdict IS that statement. The bar goes home either way, so the headline
    // is the only thing that can tell a planner which happened.
    const unpriced = outcome === "no_verdict";
    const headline = unpriced ? "Couldn't price this"
      : returnHome ? "Can't go here" : _deltaHeadline(result);
    const status = {
      verdict: "verdict · proven within budget",
      feasible_unproven: "flagged · bound not proven",
      no_verdict: "beat 2 · ran out of budget, not a verdict",
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
    const alwaysVisible = returnHome ? _refusalHtml(result, { nameOf, woOf }) : [
      _attributionHtml(result),
      _opportunityHtml(result),
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
        <span class="dc-outcome ${outcome}${unpriced ? " failure" : returnHome ? " impossible" : ""}">${headline}</span>
        <span class="dc-status">${status}</span>
      </div>
      ${returnHome ? `<div class="dc-reason"></div>` : ""}
      ${unpriced ? `<div class="dc-note unpriced">nothing is claimed about the
        placement itself — the re-solve simply did not finish. The plan is
        unchanged.</div>` : ""}
      ${alwaysVisible}
      ${detail}
      <div class="dc-actions">
        ${unpriced ? `<button class="dc-retry">Try again</button>` : ""}
        ${returnHome ? "" : `<button class="dc-accept">Accept</button>`}
        ${returnHome ? "" : `<button class="dc-askwhy">Ask why</button>`}
        <button class="dc-discard">Discard</button>
      </div>`;

    // The server's own authored sentence, set as TEXT (never interpolated into
    // markup): it can carry a solver reason and must not be able to inject any.
    if (returnHome) {
      card.querySelector(".dc-reason").textContent =
        String(result.message || "couldn't verify this placement");
    }
    const retryBtn = card.querySelector(".dc-retry");
    if (retryBtn) retryBtn.addEventListener("click", () => onRetry && onRetry());
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
    // Clause (4): the opportunity's review button is a DIFFERENT button from
    // Accept, wired to a DIFFERENT callback. One click cannot commit both.
    const reviewBtn = card.querySelector(".dc-review-search");
    if (reviewBtn) reviewBtn.addEventListener(
      "click", () => onSearchDeeper && onSearchDeeper());
    for (const b of card.querySelectorAll(".dc-line")) {
      b.addEventListener("click", () => onNavigate && onNavigate(b.dataset.op));
    }
    // R-T2(3): a perceivable ghost→card transition. Retrigger the class.
    if (opts.superseded) { void card.offsetWidth; card.classList.add("superseded"); }
    return card;
  }

  // THE ATTRIBUTION (CU1, Session 4B.5) — the first thing under the headline,
  // because it is what makes the headline readable.
  //
  // The headline is the delta of the RE-SOLVE. Two different gestures on the same
  // incumbent produced identical headlines (−$11,975.83 to the cent, twice), and
  // both were true: almost all of it was the window re-optimizing under a fresh
  // budget the incumbent had never been given. The card now says which part of
  // that number is the planner's — measured against a BASELINE solve of the same
  // window with no pin at all, never against the stale incumbent.
  //
  // When the baseline could not be proven inside the budget there is no split to
  // show, and the card says THAT rather than presenting a fused number as though
  // it were attributable. There is no third state: the split is either drawn or
  // its absence is stated.
  function _attributionHtml(result) {
    const rows = attributionRows(result);
    if (rows) {
      const note = result.attribution === "local"
        ? `<div class="dc-split-note local">${LOCAL_NOTE}</div>` : "";
      return `<div class="dc-split${result.attribution === "local" ? " local" : ""}">`
        + rows.map((r) =>
          `<div class="dc-split-row${r.own ? " your-move" : ""}">
            <span class="dc-split-k">${r.key}</span>
            <span class="dc-split-v">${signedMoney(r.value)}</span>
          </div>`).join("") + note + `</div>`;
    }
    if (result.cost_delta_abs == null) return "";   // no dollars to attribute
    const why = (result.attribution_note || "").trim();
    const el = document.createElement("div");
    el.className = "dc-split unsplit";
    el.innerHTML = `<div class="dc-split-note">${UNSPLIT_NOTE}</div>`;
    if (why && why !== UNSPLIT_NOTE) {
      const d = document.createElement("div");
      d.className = "dc-split-why";
      d.textContent = why;                  // a server string — never innerHTML
      el.appendChild(d);
    }
    return el.outerHTML;
  }

  // A PROVEN refusal from the local pricer (Session 4B.24). The headline and the
  // `dc-reason` already carry the authored sentence; this adds the two things a
  // planner acts on — WHICH job is in the way, and whether "no" means "no" or
  // "not without moving other work". The second is the whole point: a refusal
  // caused by holding the rest of the plan still is a fact about this PRICE, and
  // saying it as a fact about the PLANT would be the same fusion in a new place.
  function _refusalHtml(result, { nameOf, woOf }) {
    const r = result && result.refusal;
    if (!r) return "";
    const el = document.createElement("div");
    el.className = `dc-refusal ${r.holds_others ? "held" : "plant"}`;
    const bits = [];
    const wo = (r.other_work_orders || [])[0]
      || (r.other_op_ref && (woOf && woOf(r.other_op_ref)));
    if (wo) bits.push(`${wo} is there`);
    if (r.resource_id && nameOf) bits.push(`on ${nameOf(r.resource_id)}`);
    if (r.at) bits.push(`from ${_shortDate(r.at)}`);
    const who = document.createElement("div");
    who.className = "dc-refusal-who";
    who.textContent = bits.join(" ");
    if (bits.length) el.appendChild(who);
    const scope = document.createElement("div");
    scope.className = "dc-refusal-scope";
    scope.textContent = r.holds_others
      ? "this price holds every other job still — the scheduler may be able to "
        + "make room, which is a different question"
      : "this one does not depend on how the rest of the plan is arranged";
    el.appendChild(scope);
    return el.outerHTML;
  }

  // THE WINDOW'S OPPORTUNITY (clause 3) — its own section, its own delta, its own
  // affected list, its own accept. It is the SEARCH's discovery about the window,
  // never the planner's move, and the two must never be added together.
  function _opportunityHtml(result) {
    const o = opportunityBlock(result);
    if (!o) return "";
    const rows = o.affected.slice(0, 4).map((a) =>
      `<div class="dc-affected-row"><span class="dc-wo">${a.work_order || ""}</span>
       <span class="dc-affected-v">${signedMoney(a.tardiness_delta)}</span></div>`).join("");
    return `<div class="dc-opportunity">
      <div class="dc-opportunity-head">the search also found</div>
      <div class="dc-opportunity-line">${o.sentence}</div>
      ${rows ? `<div class="dc-affected">${rows}</div>` : ""}
      <button class="dc-review-search">Review that separately</button>
    </div>`;
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
      const tstr = (t != null && Math.abs(t) >= 0.005) ? signedMoney(t) : "";
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
    const decompHtml = lines.length ? lines.map((l) =>
      `<div class="dc-costline"><span>${l.line}</span><span>${signedMoney(l.delta)}</span></div>`
    ).join("") : "";
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
    const delta = td != null ? ` · ${signedMoney(td)}` : "";
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
      return `${pct}${signedMoney(cAbs)}`;
    }
    // no ledger dollars → relative objective change only, labelled honestly
    const d = result.delta_pct;
    if (d == null) return "Feasible";
    if (Math.abs(d) < 1e-6) return "Same plan";
    return `${d > 0 ? "+" : "−"}${Math.abs(d).toFixed(2)}% vs current plan`;
  }

  // --- Session 4B.24, clause (5): "search deeper" -------------------------

  // Session 4B.29 Item 1(d). 4B.25 §7(c): "search deeper" now costs several
  // minutes across SEVERAL searches and nothing on this surface said so — a
  // planner pressed a button expecting a re-solve and got a portfolio. The
  // scale (member count, expected minutes, the whole sentence) is composed
  // SERVER-SIDE on /meta and rendered here as TEXT; the JS never words a claim
  // about how long our own search takes, exactly as it never words the cost
  // proof.
  //
  // WHAT THIS DELIBERATELY DOES NOT SAY IS "running search 2 of 3". The audit
  // is one request with no progress channel, so a member counter here would be
  // an animation pretending to be telemetry. The ELAPSED clock below is real —
  // it counts this browser's own wall — and it is measured against the declared
  // expectation rather than against nothing.
  function showSearching(scale) {
    _stopCountdown();
    const k = scale && scale.k;
    card.className = "delta-card searching";
    card.innerHTML = `
      <div class="dc-head">
        <span class="dc-outcome">Searching deeper…</span>
        <span class="dc-status">${k > 1 ? `deterministic · ${k} seeded searches`
                                        : "deterministic · seeded"}</span>
      </div>
      <div class="dc-note dc-search-scale"></div>
      <div class="dc-note dc-search-elapsed"></div>
      <div class="dc-actions"><button class="dc-discard">Discard</button></div>`;
    // authored server text, as TEXT — never interpolated into markup
    card.querySelector(".dc-search-scale").textContent =
      String((scale && scale.sentence) ||
             "this runs the same search that produced the plan, at a bigger " +
             "budget. It changes nothing on its own — anything it finds comes " +
             "back as an offer.");
    const expect = scale && scale.expected_minutes;
    const elapsedEl = card.querySelector(".dc-search-elapsed");
    const t0 = Date.now();
    const tick = () => {
      const s = Math.round((Date.now() - t0) / 1000);
      const mm = String(Math.floor(s / 60)).padStart(2, "0");
      const ss = String(s % 60).padStart(2, "0");
      elapsedEl.textContent = expect
        ? `${mm}:${ss} elapsed of about ${expect} min expected`
        : `${mm}:${ss} elapsed`;
    };
    tick();
    countdownTimer = setInterval(tick, 1000);
    card.querySelector(".dc-discard").addEventListener(
      "click", () => onDiscard && onDiscard());
    card.classList.remove("hidden");
    return card;
  }

  // The audit's answer. THREE outcomes and none of them silent: an OFFER, the
  // incumbent-held sentence, or "I could not search" — and the third must never
  // be allowed to read as the second, because "we found nothing" and "we could
  // not look" are different facts and only one of them is about the plan.
  function showAudit(res) {
    _stopCountdown();
    const offer = res && res.offer;
    const failed = res && res.searched === false;
    const pf = portfolioLine(res);
    card.className = `delta-card audit ${offer ? "offer" : failed ? "return-home" : "held"}`;
    const rows = (offer ? offer.affected_orders || [] : []).slice(0, 4).map((a) =>
      `<div class="dc-affected-row"><span class="dc-wo">${a.work_order || ""}</span>
       <span class="dc-affected-v">${signedMoney(a.tardiness_delta)}</span></div>`).join("");
    card.innerHTML = `
      <div class="dc-head">
        <span class="dc-outcome${offer ? "" : failed ? " failure" : ""}">${
          offer ? "A cheaper schedule exists" : failed ? "Couldn't search" : "The plan held"}</span>
        <span class="dc-status">${
          failed ? "no answer"
          : pf ? `searched · ${pf.k} seeds · ${res.det_time_s} units each`
               : `searched · seed ${res.seed} · ${res.det_time_s} units`}</span>
      </div>
      <div class="dc-audit-sentence"></div>
      ${pf ? `<div class="dc-note portfolio-spread"></div>` : ""}
      ${offer ? `<div class="dc-split"><div class="dc-split-row your-move">
          <span class="dc-split-k">the search's saving</span>
          <span class="dc-split-v">${signedMoney(offer.delta_abs)}</span>
        </div><div class="dc-split-note local">this is the SEARCH's discovery about
          the window, not a move you made — accepting it is its own decision</div>
        </div>
        <div class="dc-note">${offer.moved_op_count} operation(s) would move</div>
        ${rows ? `<div class="dc-affected">${rows}</div>` : ""}` : ""}
      <div class="dc-actions">
        ${offer ? `<button class="dc-accept-search">Accept this schedule</button>` : ""}
        <button class="dc-discard">Close</button>
      </div>`;
    // authored server text, as TEXT — never interpolated into markup
    card.querySelector(".dc-audit-sentence").textContent =
      String((res && res.sentence) || "");
    // Server-composed, as TEXT. The JS never words the spread: five searches
    // agreeing and five scattering are different claims about the board, and
    // which one this is gets decided in `portfolio.agreement_sentence`.
    const spread = card.querySelector(".portfolio-spread");
    if (spread) spread.textContent = pf.text;
    const acc = card.querySelector(".dc-accept-search");
    if (acc) acc.addEventListener("click", () => {
      acc.disabled = true; acc.textContent = "accepting…";
      onAcceptSearch && onAcceptSearch();
    });
    card.querySelector(".dc-discard").addEventListener(
      "click", () => onDiscard && onDiscard());
    card.classList.remove("hidden");
    return card;
  }

  function showAuditAccepted(res) {
    card.className = "delta-card accepted";
    card.innerHTML = `
      <div class="dc-head">
        <span class="dc-outcome">Search result accepted</span>
        <span class="dc-status">new proposed version</span>
      </div>
      <div class="dc-note">this committed the SEARCH's schedule. Any move of
        your own is a separate decision.</div>
      <div class="dc-actions"><button class="dc-discard">Close</button></div>`;
    card.querySelector(".dc-discard").addEventListener(
      "click", () => onDiscard && onDiscard());
    return card;
  }

  return { showPending, showPricing, showResult, showAccepted, showPublished,
           showRefused, showImpossible, showFailure, showSearching, showAudit,
           showAuditAccepted, hide, el: card };
}
