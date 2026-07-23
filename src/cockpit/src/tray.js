// The BEYOND-HORIZON TRAY (Session 4B.3a CU2/(d)): a deliberately simple docked
// panel listing admitted-but-unscheduled future work — known Demands with no
// placement yet, so they have no bar to draw. The tray is the ghost-job answer at
// board level: known work is ALWAYS visible somewhere, so no schedulable demand
// can be silently invisible (the Glass Box cardinal danger). It is NOT on the
// timeline (no placement to draw). Empty state shows zero — NEVER hidden — so an
// empty tray reads "nothing is beyond the horizon", not "there is no tray".
//
// Read-only: renders from doc.rolling.beyond_horizon; touches no state.

const fmtDue = (iso) => {
  if (iso == null) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—"
    : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
};

// Present only on a rolling document; a monolithic board mounts no tray.
export function mountTray(hostEl, doc) {
  const rolling = doc && doc.rolling;
  if (!rolling) return null;
  const items = rolling.beyond_horizon || [];

  const el = document.createElement("div");
  el.className = "beyond-tray";
  el.id = "beyond-tray";

  const head = document.createElement("div");
  head.className = "bt-head";
  head.innerHTML =
    `<span class="bt-title">Beyond the horizon</span>`
    + `<span class="bt-count" title="known work not yet in a window">${items.length}</span>`;
  el.appendChild(head);

  const body = document.createElement("div");
  body.className = "bt-body";
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "bt-empty";
    empty.textContent = "Nothing beyond the horizon — every known order is in the current window.";
    body.appendChild(empty);
  } else {
    for (const it of items) {
      const row = document.createElement("div");
      row.className = "bt-row";
      const name = it.work_order || (it.demand_ref || "").slice(0, 8) || "—";
      row.innerHTML =
        `<span class="bt-name"></span>`
        + `<span class="bt-due" title="due date">due ${fmtDue(it.due)}</span>`;
      row.querySelector(".bt-name").textContent = name;
      if (it.customer_name) row.title = it.customer_name;
      body.appendChild(row);
    }
  }
  el.appendChild(body);
  hostEl.appendChild(el);
  return {
    el,
    count: items.length,
    // harness probe: the rendered tray's count badge + the row names shown.
    probe() {
      return {
        count: parseInt(el.querySelector(".bt-count").textContent, 10),
        empty: !!el.querySelector(".bt-empty"),
        names: [...el.querySelectorAll(".bt-name")].map((n) => n.textContent),
      };
    },
  };
}
