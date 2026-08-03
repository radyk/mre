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
import { fmt } from "./clock.js";

// R-TZ1 (Session 4B.35): every one of these renders in the DECLARED facility
// clock. They used to render in the BROWSER's, which put the hover card five
// hours from the testimony about the same bar.
const fmtDay = (iso) => fmt(iso, {
  month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false,
});

// clock time (CU4): "17:00" — for the closed/idle WINDOW span on a downtime card.
const fmtHM = (msVal) => fmt(msVal, {
  hour: "2-digit", minute: "2-digit", hour12: false,
});
// weekday + time (CU4): "Mon 05:00" — for "reopens …".
const fmtWeekdayTime = (msVal) => fmt(msVal, {
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

// Session 4B.14 Item 4: a WORKING duration in the register a planner reads —
// "7h11m", "45m", "1d 1h". Distinct from fmtSlack, which is signed and relative
// to a due date; this one is an absolute quantity of work or of elapsed time.
const fmtDur = (min) => {
  if (min == null) return "—";
  const m = Math.round(min);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60), r = m % 60;
  if (h < 24) return r ? `${h}h${String(r).padStart(2, "0")}m` : `${h}h`;
  const d = Math.floor(h / 24), rh = h % 24;
  return rh ? `${d}d ${rh}h` : `${d}d`;
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

  // Session 4B.34 Item 3(a) — A TOOLTIP NEVER COVERS ITS OWN SUBJECT.
  //
  // The card used to be placed at pointer + (14, 14) and flipped only when it
  // would leave the HOST. That keeps it on screen and says nothing about the one
  // rectangle it must not sit on: the bar it is describing. A planner hovering a
  // bar to read its dates had the bar disappear under the answer.
  //
  // The rule is the brief's: flip to the side of the SUBJECT with the most free
  // space. Horizontal first (a board is wider than it is tall and the rows are
  // short), vertical as the fallback when neither side has room — and the
  // no-intersection test is what decides, not an assumption that the flip worked.
  const GAP = 12;
  const hits = (a, b) => !(a.right <= b.left || b.right <= a.left
                        || a.bottom <= b.top || b.bottom <= a.top);

  function place(clientX, clientY, subject) {
    const host = hostEl.getBoundingClientRect();
    const cw = card.offsetWidth || 240, ch = card.offsetHeight || 120;
    let x = clientX - host.left + 14;
    let y = clientY - host.top + 14;

    if (subject) {
      const roomLeft = subject.left - host.left;
      const roomRight = host.right - subject.right;
      if (roomRight >= cw + GAP) x = subject.right - host.left + GAP;
      else if (roomLeft >= cw + GAP) x = subject.left - host.left - cw - GAP;
      else x = roomRight >= roomLeft ? host.width - cw - 4 : 4;
    }
    if (y + ch > host.height) y = host.height - ch - 8;
    x = Math.min(Math.max(4, x), Math.max(4, host.width - cw - 4));
    y = Math.min(Math.max(4, y), Math.max(4, host.height - ch - 4));

    // Neither side had room — so clear the subject VERTICALLY instead. Checked,
    // never assumed: if the flip still overlaps we take the roomier edge and say
    // so by moving there, rather than leaving the card on top of the bar.
    if (subject) {
      const box = { left: host.left + x, right: host.left + x + cw,
                    top: host.top + y, bottom: host.top + y + ch };
      if (hits(box, subject)) {
        const roomAbove = subject.top - host.top;
        const roomBelow = host.bottom - subject.bottom;
        y = roomBelow >= ch + GAP ? subject.bottom - host.top + GAP
          : roomAbove >= ch + GAP ? subject.top - host.top - ch - GAP
          : (roomBelow >= roomAbove ? host.height - ch - 4 : 4);
        y = Math.min(Math.max(4, y), Math.max(4, host.height - ch - 4));
      }
    }
    card.style.left = `${x}px`;
    card.style.top = `${y}px`;
  }

  // The subject rectangles, in CLIENT coordinates. Both are read from the
  // renderer that already owns the geometry — vis's own item DOM for a bar, and
  // vis's own `toScreen` + group foreground for a capacity band — so nothing here
  // re-derives a position the board already knows (4B.28's rule about not
  // keeping a second coordinate system in step).
  function barRect(itemId) {
    try {
      const it = timeline.itemSet.items[itemId];
      const el = it && it.dom && (it.dom.box || it.dom.point);
      return el ? el.getBoundingClientRect() : null;
    } catch { return null; }
  }
  function bandRect(resourceId, band) {
    try {
      const grp = timeline.itemSet.groups[resourceId];
      const row = grp && grp.dom && grp.dom.foreground;
      if (!row) return null;
      const r = row.getBoundingClientRect();
      const cc = center.getBoundingClientRect();
      const x0 = cc.left + timeline.body.util.toScreen(new Date(band.start));
      const x1 = cc.left + timeline.body.util.toScreen(new Date(band.end));
      return { left: Math.min(x0, x1), right: Math.max(x0, x1),
               top: r.top, bottom: r.bottom };
    } catch { return null; }
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
    // Session 4B.14 Item 4 — RUN TIME AND ELAPSED SPAN, DISTINCTLY LABELLED.
    //
    // After 4B.13's chunk fix these genuinely differ (ORD-000011 is 1,501
    // working minutes across a 5,821-minute span) and that difference IS the
    // answer to half the "why is there a gap" questions. Two labelled rows, and
    // "Elapsed" only appears when it is actually longer than the run — on an
    // unbroken operation the two are the same number and printing it twice is
    // noise. Confirming any of this used to mean zooming and counting pixels.
    const runTxt = fmtDur(job.runMin);
    const showElapsed = job.spanMin != null && job.runMin != null
      && job.spanMin - job.runMin >= 1;
    const elapsedRow = showElapsed
      ? `<dt>Elapsed</dt><dd class="hc-elapsed">${fmtDur(job.spanMin)}` +
        `<span class="hc-note"> — ${fmtDur(job.spanMin - job.runMin)} paused` +
        (job.chunkCount > 1 ? `, ${job.chunkCount} pieces` : "") + `</span></dd>`
      : "";
    // What decides whether this operation can take a short window. Omitted
    // entirely when the document does not carry it (pre-1.12): a card that
    // guessed a default here would be the confident-wrong class again.
    const splitRow = job.splittable == null ? ""
      : `<dt>Splitting</dt><dd class="hc-split">` +
        (job.splittable
          ? "can be split" + (job.minChunkMin
              ? ` — pieces of at least ${fmtDur(job.minChunkMin)}` : "")
          : "cannot be split — needs one unbroken window") + `</dd>`;
    card.className = `hover-card job ${statusCls}`;
    card.innerHTML = `
      <div class="hc-head"><span class="hc-order"></span>
        <span class="hc-status ${statusCls}">${statusTxt}</span></div>
      <dl class="hc-grid">
        <dt>When</dt><dd class="hc-when"></dd>
        <dt>Run time</dt><dd class="hc-run">${runTxt}</dd>
        ${elapsedRow}
        ${splitRow}
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
      if (job) { jobCard(job); place(ev.clientX, ev.clientY, barRect(props.item)); return; }
    }
    // otherwise a capacity band on the hovered row?
    const rid = props.group ?? null;
    const t = props.time ? props.time.getTime() : null;
    if (rid != null && t != null) {
      const band = ctx.bandAt(rid, t);
      if (band && band.kind !== "openidle") {   // openidle: leave the board clean
        downtimeCard(band, ctx.reopenMinutes(rid, band), ctx.resourceName(rid));
        place(ev.clientX, ev.clientY, bandRect(rid, band));
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
    // It now PLACES as well as renders — a probe that skipped placement would be
    // testing the card's prose and calling it a test of where the card goes.
    _showJob(assignmentId) {
      const j = ctx.jobFor(assignmentId);
      if (!j) return false;
      jobCard(j);
      const r = barRect(assignmentId);
      if (r) place(r.left + r.width / 2, r.top + r.height / 2, r);
      return true;
    },
    // harness: the subject rectangle the card was placed against, so a guard can
    // assert the no-overlap invariant on the pair rather than on the card alone.
    _subjectRect: barRect,
    _showBand(resourceId, timeMs) {
      const b = ctx.bandAt(resourceId, timeMs);
      if (b && b.kind !== "openidle") { downtimeCard(b, ctx.reopenMinutes(resourceId, b), ctx.resourceName(resourceId)); return b.kind; }
      return null;
    },
    isShown() { return shown; },
  };
}
