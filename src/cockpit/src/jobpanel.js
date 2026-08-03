// THE JOB PANEL (Session 4B.28 Item 3) — click a bar, see the whole job.
//
// Selection already lit the lanes; this is the missing half. A planner clicking
// one bar of a five-operation order was shown that bar and nothing about the
// four it belongs to — so "where is the rest of this job" meant hunting rows.
//
// EVERY QUANTITY COMES FROM THE BOARD'S OWN DERIVATION (board.jobRowsForOrder,
// which is `jobFor` — the same function the hover card reads). Nothing here
// computes a duration, a band or a disposition. That is 4B.21's discipline and
// it is not decoration: five of the last six category fusions in this product
// were a name written once, by whoever needed a number, and never re-read as a
// claim. A panel that recomputed working time would be the sixth.
//
// WORKING TIME AND SPAN ARE NAMED SEPARATELY AND ONLY SHOWN TOGETHER WHEN THEY
// DIFFER (4B.20's ruling). On an unchunked operation they are the same number
// and printing both would invite a planner to look for a difference that is not
// there.

const MIN_LABEL = { committed: "committed", active_window: "active" };

function fmtClock(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
    hour12: false,
  });
}
function fmtDay(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—"
    : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
function fmtMin(m) {
  if (m == null) return "—";
  const h = Math.floor(m / 60), r = Math.round(m % 60);
  return h ? `${h}h${r ? ` ${r}m` : ""}` : `${r}m`;
}

export function createJobPanel(hostEl, board, opts = {}) {
  const el = document.createElement("div");
  el.className = "job-panel hidden";
  el.id = "job-panel";
  hostEl.appendChild(el);

  let current = null;     // {order, opRef}

  // Session 4B.34 Item 3(b) — A PERSISTENT PANEL IS DRAGGABLE, A TRANSIENT ONE
  // IS SMART-POSITIONED. Two classes, two behaviours, and this is the persistent
  // one: it stays until dismissed, so the planner — not an algorithm — decides
  // where it lives. It opens anchored top-right and can cover the very bars it
  // describes; a tooltip solves that by flipping, but a panel that flipped under
  // the pointer while being read would be worse than the occlusion.
  //
  // The position is owned HERE, outside the subtree `show()` rebuilds, and
  // reapplied on every render — the 4B.28 boundary-grip lesson: state that lives
  // in a node a redraw recreates is state a redraw destroys.
  let pos = null;                       // {left, top} in host coords, or null

  function applyPos() {
    if (pos) {
      el.style.left = `${pos.left}px`;
      el.style.top = `${pos.top}px`;
      el.style.right = "auto";
    } else {
      el.style.left = el.style.top = el.style.right = "";
    }
  }

  // The drag enters through the USER'S DOOR: a real pointerdown on the header,
  // exactly where a hand would land. 4B.28 §5a.123 is why this matters — a
  // control driven past its own entry point is a control nothing proved.
  function onHeadPointerDown(ev) {
    if (ev.button !== 0) return;
    if (ev.target.closest("button")) return;      // ✕ and the row actions win
    const box = el.getBoundingClientRect();
    const host = hostEl.getBoundingClientRect();
    const dx = ev.clientX - box.left, dy = ev.clientY - box.top;
    pos = { left: box.left - host.left, top: box.top - host.top };
    applyPos();
    el.classList.add("dragging");
    ev.preventDefault();
    const move = (e) => {
      const h = hostEl.getBoundingClientRect();
      // clamped so the panel can never be dragged out of reach of the hand that
      // dragged it — the header always stays grabbable.
      pos = {
        left: Math.min(Math.max(0, e.clientX - h.left - dx), Math.max(0, h.width - box.width)),
        top: Math.min(Math.max(0, e.clientY - h.top - dy), Math.max(0, h.height - 28)),
      };
      applyPos();
    };
    const up = () => {
      el.classList.remove("dragging");
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  function hide() {
    el.classList.add("hidden");
    el.replaceChildren();
    current = null;
    // An explicit dismissal retires the placement too: the next selection opens
    // a fresh panel at the anchor, not wherever the last one was parked.
    pos = null;
    applyPos();
  }

  // The DISPOSITION of one placed operation, named rather than implied. Who may
  // move it is TWO facts (the rolling commitment state and the planner's own
  // pin) and they are shown as two, because absorbing one into the other is how
  // a planner ends up unable to tell a commitment from a decision they made.
  function statusChips(row) {
    const out = [];
    if (row.commitmentState) {
      out.push({ cls: `jp-chip st-${row.commitmentState}`,
                 text: MIN_LABEL[row.commitmentState] || row.commitmentState });
    }
    if (row.standingPin) out.push({ cls: "jp-chip st-pinned", text: "pinned" });
    if (row.chunkCount > 1) {
      out.push({ cls: "jp-chip st-split", text: `${row.chunkCount} pieces` });
    }
    return out;
  }

  function renderRow(row, isSelected) {
    const r = document.createElement("div");
    r.className = `jp-row${isSelected ? " selected" : ""} late-${row.band}`;
    r.dataset.op = row.operation_ref;

    const head = document.createElement("div");
    head.className = "jp-row-head";
    const seq = document.createElement("span");
    seq.className = "jp-seq";
    seq.textContent = row.op_seq == null ? "op —" : `op ${row.op_seq}`;
    const mach = document.createElement("span");
    mach.className = "jp-mach";
    mach.textContent = row.machine;
    const badge = document.createElement("span");
    badge.className = `jp-badge late-${row.band}`;
    badge.textContent = row.band === "late" ? "late"
      : row.band === "tight" ? "tight" : "on time";
    head.append(seq, mach, badge);
    r.appendChild(head);

    const when = document.createElement("div");
    when.className = "jp-when";
    when.textContent = `${fmtClock(row.start)} → ${fmtClock(row.end)}`;
    r.appendChild(when);

    const facts = document.createElement("div");
    facts.className = "jp-facts";
    // 4B.20: name WHICH quantity, always — and show the span only where it is a
    // DIFFERENT number from the working time, which is exactly when the
    // operation is chunked.
    const work = document.createElement("span");
    work.className = "jp-fact";
    work.textContent = `working ${fmtMin(row.runMin)}`;
    facts.appendChild(work);
    if (row.chunkCount > 1 && row.spanMin != null && row.spanMin !== row.runMin) {
      const span = document.createElement("span");
      span.className = "jp-fact jp-span";
      span.textContent = `span ${fmtMin(row.spanMin)}`;
      facts.appendChild(span);
    }
    r.appendChild(facts);

    const chips = document.createElement("div");
    chips.className = "jp-chips";
    for (const c of statusChips(row)) {
      const s = document.createElement("span");
      s.className = c.cls;
      s.textContent = c.text;
      chips.appendChild(s);
    }
    if (chips.childElementCount) r.appendChild(chips);

    // Item 3's last clause — and it INCIDENTALLY DISCHARGES 4B.30 §5a.118(c)
    // for board users. `op_seq` is not parseable in text, so every multi-op
    // order's typed question answers about its FIRST operation; a panel row
    // click carries the operation exactly, with no parse in the way.
    const acts = document.createElement("div");
    acts.className = "jp-acts";
    const why = document.createElement("button");
    why.type = "button";
    why.className = "jp-why";
    why.textContent = "Why is this here?";
    why.addEventListener("click", (ev) => {
      ev.stopPropagation();
      if (opts.onAsk) opts.onAsk("why-here", row);
    });
    const what = document.createElement("button");
    what.type = "button";
    what.className = "jp-what";
    what.textContent = "What would have to change?";
    what.addEventListener("click", (ev) => {
      ev.stopPropagation();
      if (opts.onAsk) opts.onAsk("what-would-change", row);
    });
    acts.append(why, what);
    r.appendChild(acts);

    // Clicking the row navigates the BOARD to that bar — scroll + flash — and
    // moves the selection with it, so the panel and the board never disagree
    // about which operation is in focus.
    r.addEventListener("click", () => {
      board.revealOp(row.operation_ref);
      board.select(row.operation_ref);
    });
    return r;
  }

  function renderTrayRow(t) {
    const r = document.createElement("div");
    r.className = "jp-row jp-tray";
    const head = document.createElement("div");
    head.className = "jp-row-head";
    const seq = document.createElement("span");
    seq.className = "jp-seq";
    seq.textContent = "not placed";
    const badge = document.createElement("span");
    badge.className = "jp-badge st-tray";
    badge.textContent = "beyond the horizon";
    head.append(seq, badge);
    r.appendChild(head);
    const when = document.createElement("div");
    when.className = "jp-when";
    when.textContent = `due ${fmtDay(t.due)}`
      + (t.earliest ? ` · earliest window ~${fmtDay(t.earliest)}` : "");
    r.appendChild(when);
    return r;
  }

  function show(selection) {
    const order = (selection && (selection.work_orders || [])[0]) || null;
    if (!order) return hide();
    const rows = board.jobRowsForOrder(order);
    const tray = board.trayRowsForOrder(order);
    if (!rows.length && !tray.length) return hide();
    current = { order, opRef: selection.operation_ref };

    el.className = "job-panel";
    el.replaceChildren();

    const head = document.createElement("div");
    head.className = "jp-head";
    head.addEventListener("pointerdown", onHeadPointerDown);
    const title = document.createElement("span");
    title.className = "jp-title";
    title.textContent = order;
    const sub = document.createElement("span");
    sub.className = "jp-sub";
    // The count NAMES ITS DISPOSITION (4B.21): "operations" alone is not one,
    // and on a part-placed order the placed set and the known set differ.
    sub.textContent = tray.length
      ? `${rows.length} placed · ${tray.length} not yet placed`
      : `${rows.length} operation${rows.length === 1 ? "" : "s"}, all placed`;
    const close = document.createElement("button");
    close.type = "button";
    close.className = "jp-close";
    close.setAttribute("aria-label", "close job panel");
    close.textContent = "✕";
    close.addEventListener("click", hide);
    head.append(title, sub, close);
    el.appendChild(head);

    const so = board.serviceOutcomeFor(order);
    if (so) {
      const meta = document.createElement("div");
      meta.className = "jp-meta";
      const bits = [];
      if (so.customer_name) bits.push(so.customer_name);
      if (so.due) bits.push(`due ${fmtDay(so.due)}`);
      if (so.lateness_min != null) {
        bits.push(so.lateness_min > 0
          ? `${fmtMin(so.lateness_min)} late`
          : `${fmtMin(Math.abs(so.lateness_min))} of slack`);
      }
      meta.textContent = bits.join(" · ");
      el.appendChild(meta);
    }

    const body = document.createElement("div");
    body.className = "jp-body";
    for (const row of rows) {
      body.appendChild(renderRow(row, row.operation_ref === selection.operation_ref));
    }
    for (const t of tray) body.appendChild(renderTrayRow(t));
    el.appendChild(body);
    // reapply AFTER the rebuild — a data refresh re-renders the whole subtree,
    // and the placement must survive it.
    applyPos();
    return el;
  }

  return {
    el, show, hide,
    // harness probe: what the panel is actually stating, read back from state
    // rather than from the DOM's prose, plus the row count so a test can assert
    // the WHOLE job is listed rather than the clicked bar.
    probe() {
      if (!current) return { open: false };
      return {
        open: !el.classList.contains("hidden"),
        order: current.order,
        selectedOp: current.opRef,
        // Item 3(b): the placement the planner chose, read from the owner rather
        // than from the style attribute, so a guard proves the STATE survived a
        // rebuild and not merely that some inline style did.
        pos: pos ? { ...pos } : null,
        rows: [...el.querySelectorAll(".jp-row:not(.jp-tray)")].map((r) => ({
          op: r.dataset.op,
          seq: r.querySelector(".jp-seq").textContent,
          machine: (r.querySelector(".jp-mach") || {}).textContent || null,
          selected: r.classList.contains("selected"),
          facts: [...r.querySelectorAll(".jp-fact")].map((f) => f.textContent),
        })),
        trayRows: el.querySelectorAll(".jp-row.jp-tray").length,
      };
    },
  };
}
