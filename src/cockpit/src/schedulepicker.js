// The schedule picker + the schedule-list renderer (hotfix session CU2).
//
// Two pure reads (unit-tested framework-free in the `logic` harness project) and
// one DOM list renderer mounted in TWO places, deliberately:
//   * the header chip's dropdown — switch schedules without hand-editing the URL;
//   * the CU1 not-found recovery — an unknown ?schedule= names the id it could
//     not find and offers THIS list, never a silent substitution.
// One renderer, so the recovery surface IS the picker surface.
//
// Every visual value comes from tokens.css (see cockpit.css `.sched-picker`).

// Rolling (sliced-world) vs monolithic. The registry carries NO sliced column —
// the listing row (id / run_id / submission_id / snapshot_id / status /
// contract_version / created_at) says nothing directly. Two structural namings do,
// and both are minted by the sliced path itself, not by a human:
//   * src/mre/api/app.py  — a sliced solve registers ``rolling-<run_id[:12]>``;
//   * rolling_horizon.prepare_plant — its snapshot is ``snap-rolling``.
// A monolithic id is a uuid4, whose alphabet (hex + dashes) cannot spell
// "rolling", so the read has no false positives. A registry `sliced` column would
// be the durable fix; that is a schema change, not a hotfix (noted in docs/04).
const ROLLING_ID = /(^|-)rolling(-|$)/i;
export function scheduleKind(row) {
  if (!row) return "monolithic";
  if (ROLLING_ID.test(String(row.id || ""))) return "rolling";
  if (/rolling/i.test(String(row.snapshot_id || ""))) return "rolling";
  return "monolithic";
}

// The listing arrives oldest→newest (the real API is ORDER BY created_at). The
// picker shows newest FIRST — the ordering a planner reaches for. Stable: rows
// with equal or absent created_at keep the listing's own order, reversed, so a
// tie never reorders arbitrarily between opens.
export function sortNewestFirst(rows) {
  if (!Array.isArray(rows)) return [];
  return rows
    .filter((r) => r && r.id)
    .map((r, i) => {
      const t = r.created_at ? Date.parse(r.created_at) : NaN;
      return { r, i, t: Number.isNaN(t) ? null : t };
    })
    .sort((a, b) => {
      if (a.t != null && b.t != null && a.t !== b.t) return b.t - a.t;
      return b.i - a.i;
    })
    .map((x) => x.r);
}

// "Jul 26, 19:13" — date + clock, because the dev data root routinely holds
// several days of solves and a bare clock reads as "today" when it is not.
import { fmt } from "./clock.js";
export function whenLabel(row) {
  if (!row || !row.created_at) return "";
  const t = new Date(row.created_at);
  if (Number.isNaN(t.getTime())) return "";
  return fmt(t, {                                 // R-TZ1: the declared clock
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

// The short human handle. `solve #N` needs a `generation`, which the LISTING does
// not carry (only /meta does) — so the short id is the honest handle here, never
// an invented ordinal.
export function shortId(id) {
  const s = String(id || "");
  // 12 chars: enough to separate two uuid4s at a glance AND to keep a
  // `rolling-<run>` id recognisable as itself. A trailing dash is trimmed so the
  // handle never reads as truncated mid-segment.
  return s.length > 12 ? s.slice(0, 12).replace(/-$/, "") : s;
}

// R-GP1 (Session 4B.34 Item 6) — WHAT A ROW SAYS.
//
// Rows used to be a truncated id and a status, so `rolling-b4dd3010751f` — a
// re-freeze ceremony child whose placements are the Khalil demo board's to the
// character — was indistinguishable from the board it copies, and sat above it
// wearing "current". Every field below is DERIVED from documents the client
// already fetches; none of them names a new schema column.
//
// THE LEDGER IS NOT ENOUGH AND THAT IS MEASURED: on this lineage the demo board,
// both ceremony children AND a zero-move accept all read $1,667,467.80, and so
// does the one child that actually moved an operation. The BADGE is what
// separates them, and it is the placement digest that decides the badge.
const BADGE_TEXT = {
  "placements-changed": "placements changed",
  "authority-only": "authority only",
  "accepted-edit": "accepted edit · same placements",
};
const money = (n) => (n == null ? null
  : `$${Math.round(n).toLocaleString("en-US")}`);

// One row's derived line, from the facts `lineagestore` resolved. Returns null
// while nothing is known yet — a row states what it has and never fills a gap
// with a guess.
export function factsLine(facts) {
  if (!facts) return null;
  const bits = [];
  if (facts.ledger != null) bits.push(money(facts.ledger));
  if (facts.bars != null) bits.push(`${facts.bars} bars`);
  if (facts.calibrated === true) bits.push("calibrated");
  else if (facts.calibrated === false) bits.push("uncalibrated");
  if (facts.digest) bits.push(`plan ${facts.digest}`);
  return bits.length ? bits.join(" · ") : null;
}

// The list itself. Rows are buttons (keyboard-reachable, no link semantics — a
// pick is a navigation the app performs). The bound row is marked, not hidden:
// seeing where you are is half of why the list is open.
export function renderScheduleList(rows, { currentId = null, onPick, emptyText } = {}) {
  const list = document.createElement("div");
  list.className = "sched-list";
  list.setAttribute("role", "listbox");
  const ordered = sortNewestFirst(rows);
  if (!ordered.length) {
    const empty = document.createElement("div");
    empty.className = "sl-empty";
    empty.textContent = emptyText || "no schedules registered";
    list.appendChild(empty);
    return list;
  }
  for (const row of ordered) {
    const kind = scheduleKind(row);
    const isCurrent = !!currentId && row.id === currentId;
    const b = document.createElement("button");
    b.type = "button";
    b.className = `sl-row${isCurrent ? " current" : ""}`;
    b.setAttribute("role", "option");
    b.setAttribute("aria-selected", isCurrent ? "true" : "false");
    b.dataset.scheduleId = row.id;
    b.dataset.kind = kind;
    b.title = row.id;                       // the full id stays available on hover

    const id = document.createElement("span");
    id.className = "sl-id";
    id.textContent = shortId(row.id);       // textContent: an id from the URL is never HTML
    const k = document.createElement("span");
    k.className = `sl-kind ${kind}`;
    k.textContent = kind;
    const when = document.createElement("span");
    when.className = "sl-when";
    when.textContent = whenLabel(row);
    const st = document.createElement("span");
    st.className = "sl-status";
    st.textContent = isCurrent ? "current" : (row.status || "");

    b.append(id, k, when, st);
    // R-GP1: a second line for the derived facts + the lineage badge, filled in
    // by `applyRowFacts` as each document lands. It starts EMPTY rather than
    // starting wrong.
    const facts = document.createElement("span");
    facts.className = "sl-facts";
    b.appendChild(facts);
    b.addEventListener("click", () => { if (onPick) onPick(row.id); });
    list.appendChild(b);
  }
  return list;
}

// Fill one already-rendered row with its derived facts. Separate from the render
// so the list paints immediately and the 400 KB-per-document reads land behind
// it — and so a guard can drive the display from hand-built facts.
export function applyRowFacts(list, id, facts) {
  const row = list && list.querySelector(`[data-schedule-id="${CSS.escape(id)}"]`);
  if (!row) return null;
  const cell = row.querySelector(".sl-facts");
  if (!cell) return null;
  cell.replaceChildren();
  if (facts && facts.badge) {
    const badge = document.createElement("span");
    badge.className = `sl-badge b-${facts.badge}`;
    badge.textContent = BADGE_TEXT[facts.badge] || facts.badge;
    cell.appendChild(badge);
    row.dataset.badge = facts.badge;
  }
  const line = factsLine(facts);
  if (line) {
    const txt = document.createElement("span");
    txt.className = "sl-derived";
    txt.textContent = line;
    cell.appendChild(txt);
  }
  if (facts && facts.digest) row.dataset.planDigest = facts.digest;
  return cell;
}

// Mount the dropdown on the header chip. `currentId` is a FUNCTION, resolved at
// open time — a live accept/publish rebinds the board to a new version without a
// reload, and the picker must mark the version the board IS, not the one it was
// mounted with. `load` is the listing call; a failure renders the honest empty
// line rather than an empty box.
export function mountSchedulePicker(anchor, { currentId, load, onPick, decorate } = {}) {
  if (!anchor) return null;
  let panel = null;

  const close = () => {
    if (!panel) return;
    panel.remove();
    panel = null;
    anchor.setAttribute("aria-expanded", "false");
    document.removeEventListener("click", onDocClick, true);
    document.removeEventListener("keydown", onKey, true);
  };
  const onDocClick = (e) => {
    if (panel && !panel.contains(e.target) && e.target !== anchor) close();
  };
  const onKey = (e) => {
    if (e.key === "Escape") { close(); anchor.focus(); }
  };

  const open = async () => {
    if (panel) return panel;
    panel = document.createElement("div");
    panel.className = "sched-picker";
    panel.id = "sched-picker";
    const head = document.createElement("div");
    head.className = "sp-head";
    head.textContent = "schedules · newest first";
    panel.appendChild(head);
    anchor.parentElement.appendChild(panel);
    anchor.setAttribute("aria-expanded", "true");
    // listeners in the CAPTURE phase so a click on a board bar closes it too.
    document.addEventListener("click", onDocClick, true);
    document.addEventListener("keydown", onKey, true);

    let rows = [];
    try {
      const data = await load();
      rows = (data && data.schedules) || [];
    } catch { rows = []; }
    if (!panel) return null;                 // closed while the listing was in flight
    const list = renderScheduleList(rows, {
      currentId: typeof currentId === "function" ? currentId() : currentId,
      onPick: (id) => { close(); if (onPick) onPick(id); },
      emptyText: "the schedule listing is unavailable",
    });
    panel.appendChild(list);
    // R-GP1: decorate progressively. `decorate` is optional so the pure renderer
    // stays testable without a network, and a panel closed mid-flight simply
    // stops receiving rows.
    if (decorate) {
      decorate(rows, (id, facts) => {
        if (panel && list.isConnected) applyRowFacts(list, id, facts);
      }, (planCurrentId) => {
        // R-GP1: mark the row that LEADS the lineage — the newest
        // placement-bearing state — which on a board followed only by ceremony
        // children is the board itself. Distinct from `.current`, which marks
        // where the planner IS.
        if (!panel || !list.isConnected || !planCurrentId) return;
        for (const r of list.querySelectorAll(".sl-row")) delete r.dataset.planCurrent;
        const lead = list.querySelector(`[data-schedule-id="${CSS.escape(planCurrentId)}"]`);
        if (lead) lead.dataset.planCurrent = "true";
      }).catch(() => { /* a facts failure leaves the bare row, never an error box */ });
    }
    return panel;
  };

  anchor.setAttribute("aria-haspopup", "listbox");
  anchor.setAttribute("aria-expanded", "false");
  anchor.addEventListener("click", (e) => {
    e.stopPropagation();                     // never reaches onDocClick's capture
    if (panel) close(); else open();
  });

  return { open, close, isOpen: () => !!panel };
}
