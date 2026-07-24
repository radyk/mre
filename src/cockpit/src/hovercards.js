// Planner-voiced hover cards (docs/07 Session 4.2 CU3). Two cards, one floating
// element, driven by vis's OWN hit-test (getEventProperties → group + time +
// item) so the pointer maths is vis's, not ours:
//
//   JOB card       hovering a bar: order, qty, due, customer, routing position,
//                  late/tight status, and its standing-pin / lock state.
//   DOWNTIME card  hovering a closure / maintenance / off-shift band: which
//                  calendar state it is, its reason, and when the row reopens.
//
// Everything is PLANNER VOCABULARY — external order + customer names, never a
// canonical UUID (the identity map resolved those server-side). Read-only.

const fmtDay = (iso) => {
  if (iso == null) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false,
  });
};

// clock time (CU4): "17:00" — for the closed/idle WINDOW span on a downtime card.
const fmtHM = (msVal) => new Date(msVal).toLocaleString(undefined, {
  hour: "2-digit", minute: "2-digit", hour12: false,
});
// weekday + time (CU4): "Mon 05:00" — for "reopens …".
const fmtWeekdayTime = (msVal) => new Date(msVal).toLocaleString(undefined, {
  weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false,
});

// CU5a: the lateness/slack figure a planner reads a bar for. Positive = late,
// negative/zero = early slack. Minutes under an hour, hours under a day, else days.
const fmtSlack = (min) => {
  if (min == null) return "—";
  if (min > 0) {
    const m = Math.round(min);
    return m >= 1440 ? `${(m / 1440).toFixed(1)}d late`
      : m >= 60 ? `${(m / 60).toFixed(1)}h late` : `${m} min late`;
  }
  const e = Math.round(-min);
  if (e <= 0) return "on its due date";
  return e >= 1440 ? `${(e / 1440).toFixed(1)}d early`
    : e >= 60 ? `${(e / 60).toFixed(1)}h early` : `${e} min early`;
};

const CLOSURE_LABEL = {
  planned_maintenance: "Planned maintenance",
  breakdown: "Recorded downtime",
  holiday: "Holiday closure",
};
const bandTitle = (band) => {
  if (band.kind === "maintenance") return "Planned maintenance";
  if (band.kind === "closure") return CLOSURE_LABEL[band.reason] || "Calendar closure";
  if (band.kind === "offshift") return "Off shift";
  if (band.kind === "openidle") return "Open — idle capacity";
  if (band.kind === "overtime") return "Overtime shift";
  return "Non-working";
};

export function createHoverCards(hostEl, timeline, ctx) {
  // ctx: { jobFor(assignmentId) -> {order, qty, uom, due, customer, opSeq,
  //          status, standingPin, resourceName}|null,
  //        bandAt(resourceId, timeMs) -> {kind, reason, start, end}|null,
  //        reopenMinutes(resourceId, band) -> minutes|null }
  const card = document.createElement("div");
  card.className = "hover-card hidden";
  card.setAttribute("role", "tooltip");
  hostEl.appendChild(card);
  const center = timeline.dom.centerContainer;

  let shown = false;
  function hide() { if (shown) { card.className = "hover-card hidden"; shown = false; } }
  function place(clientX, clientY) {
    const host = hostEl.getBoundingClientRect();
    let x = clientX - host.left + 14;
    let y = clientY - host.top + 14;
    // keep the card inside the board host
    const cw = card.offsetWidth || 240, ch = card.offsetHeight || 120;
    if (x + cw > host.width) x = clientX - host.left - cw - 14;
    if (y + ch > host.height) y = host.height - ch - 8;
    card.style.left = `${Math.max(4, x)}px`;
    card.style.top = `${Math.max(4, y)}px`;
  }

  function jobCard(job) {
    const pin = job.standingPin
      ? `<div class="hc-pin">📌 committed — accepted edit (held)</div>` : "";
    const statusCls = job.status === "late" ? "late" : job.status === "tight" ? "tight" : "ontime";
    const statusTxt = job.status === "late" ? "LATE" : job.status === "tight" ? "TIGHT" : "on time";
    const qty = job.qty != null ? `${job.qty}${job.uom ? " " + job.uom : ""}` : "—";
    // CU5a: the bar's span and its lateness/slack figure — the two facts a planner
    // reads a bar for. Span "Jan 6 07:00 → 14:50"; slack "890 min late" / "0.2d early".
    const span = (job.start != null && job.end != null)
      ? `${fmtDay(job.start)} → ${fmtDay(job.end)}` : "—";
    const slack = fmtSlack(job.latenessMin);
    card.className = `hover-card job ${statusCls}`;
    card.innerHTML = `
      <div class="hc-head"><span class="hc-order"></span>
        <span class="hc-status ${statusCls}">${statusTxt}</span></div>
      <dl class="hc-grid">
        <dt>When</dt><dd class="hc-when"></dd>
        <dt>Slack</dt><dd class="hc-slack">${slack}</dd>
        <dt>Qty</dt><dd class="hc-qty"></dd>
        <dt>Customer</dt><dd class="hc-cust"></dd>
        <dt>Due</dt><dd>${fmtDay(job.due)}</dd>
        <dt>Routing</dt><dd>op&nbsp;${job.opSeq}</dd>
        <dt>Machine</dt><dd class="hc-res"></dd>
      </dl>${pin}`;
    card.querySelector(".hc-order").textContent = job.order || "—";
    card.querySelector(".hc-when").textContent = span;
    card.querySelector(".hc-qty").textContent = qty;
    card.querySelector(".hc-cust").textContent = job.customer || "—";
    card.querySelector(".hc-res").textContent = job.resourceName || "—";
    shown = true;
  }

  function downtimeCard(band, reopenMin, resourceName) {
    card.className = `hover-card downtime ${band.kind}`;
    // CU4: state the WINDOW ("17:00 – 05:00") and the reopen time ("reopens Mon
    // 05:00") — a downtime card should say when it closed and when it lifts.
    const windowLine = `<div class="hc-sub">${fmtHM(band.start)} – ${fmtHM(band.end)}</div>`;
    const reopenLine = band.kind === "openidle"
      ? `<div class="hc-sub">available now — no work booked here</div>`
      : (reopenMin != null
          ? `<div class="hc-sub">reopens <b>${fmtWeekdayTime(band.start + reopenMin * 60000)}</b></div>`
          : `<div class="hc-sub">no further open window this horizon</div>`);
    card.innerHTML = `
      <div class="hc-head"><span class="hc-dt-title">${bandTitle(band)}</span></div>
      <div class="hc-sub hc-res"></div>
      ${band.kind === "openidle" ? "" : windowLine}
      ${reopenLine}`;
    card.querySelector(".hc-res").textContent = resourceName || "";
    shown = true;
  }

  function onMove(ev) {
    let props;
    try { props = timeline.getEventProperties(ev); } catch { return hide(); }
    if (!props || props.what === "axis" || props.what === "group-label") return hide();
    // a bar under the pointer?
    if (props.item != null) {
      const job = ctx.jobFor(props.item);
      if (job) { jobCard(job); place(ev.clientX, ev.clientY); return; }
    }
    // otherwise a capacity band on the hovered row?
    const rid = props.group ?? null;
    const t = props.time ? props.time.getTime() : null;
    if (rid != null && t != null) {
      const band = ctx.bandAt(rid, t);
      if (band && band.kind !== "openidle") {   // openidle: leave the board clean
        downtimeCard(band, ctx.reopenMinutes(rid, band), ctx.resourceName(rid));
        place(ev.clientX, ev.clientY);
        return;
      }
    }
    hide();
  }

  center.addEventListener("mousemove", onMove);
  center.addEventListener("mouseleave", hide);

  return {
    el: card, hide,
    // harness: force a render of a job card by assignment id (no real pointer).
    _showJob(assignmentId) { const j = ctx.jobFor(assignmentId); if (j) { jobCard(j); return true; } return false; },
    _showBand(resourceId, timeMs) {
      const b = ctx.bandAt(resourceId, timeMs);
      if (b && b.kind !== "openidle") { downtimeCard(b, ctx.reopenMinutes(resourceId, b), ctx.resourceName(resourceId)); return b.kind; }
      return null;
    },
    isShown() { return shown; },
  };
}
