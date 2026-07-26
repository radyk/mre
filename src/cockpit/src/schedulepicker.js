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
export function whenLabel(row) {
  if (!row || !row.created_at) return "";
  const t = new Date(row.created_at);
  if (Number.isNaN(t.getTime())) return "";
  return t.toLocaleString([], {
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
    b.addEventListener("click", () => { if (onPick) onPick(row.id); });
    list.appendChild(b);
  }
  return list;
}

// Mount the dropdown on the header chip. `currentId` is a FUNCTION, resolved at
// open time — a live accept/publish rebinds the board to a new version without a
// reload, and the picker must mark the version the board IS, not the one it was
// mounted with. `load` is the listing call; a failure renders the honest empty
// line rather than an empty box.
export function mountSchedulePicker(anchor, { currentId, load, onPick } = {}) {
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
    panel.appendChild(renderScheduleList(rows, {
      currentId: typeof currentId === "function" ? currentId() : currentId,
      onPick: (id) => { close(); if (onPick) onPick(id); },
      emptyText: "the schedule listing is unavailable",
    }));
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
