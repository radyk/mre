// The question-ledger refusal view (Session 4A.1 CU3, R-AI1(d)) — a DEV-panel,
// gated exactly like the feel tuning panel (mounted only when import.meta.env.DEV
// is true; never in the production `vite build` the harness serves).
//
// It lists the refusal clusters ranked by frequency — the human-curated
// improvement loop's window onto what planners asked that the system couldn't
// answer. Per R-AI1(d) the system never rewrites its own routing from this;
// a human reads the clusters and curates the taxonomy / paraphrase table.
//
// The endpoint (`GET /ledger/refusals`) is itself DEV-gated server-side (404
// unless MRE_DEV is set), so a missing panel simply means "no dev ledger" — never
// an error surfaced to the planner.
import { ledgerRefusals } from "./api.js";

export function mountDevLedger(hostEl) {
  const panel = document.createElement("div");
  // Docked bottom-LEFT (board side) and COLLAPSED by default (session 4.0c) so it
  // never occludes the ask composer on the right — it opens only when a developer
  // clicks it. The header toggles; the body (including the empty/"no dev ledger"
  // state) lives INSIDE the docked panel, never floating over ask.
  panel.className = "dev-ledger collapsed";
  panel.innerHTML = `
    <div class="dl-head">
      <button class="dl-toggle" title="show / hide the refusal ledger" aria-expanded="false">
        <span class="dl-chevron">▸</span>
        <span class="dl-title">question ledger · refusals</span>
      </button>
      <button class="dl-refresh" title="reload">↻</button>
    </div>
    <div class="dl-body"><div class="dl-empty">loading…</div></div>`;
  hostEl.appendChild(panel);
  const body = panel.querySelector(".dl-body");

  const toggleBtn = panel.querySelector(".dl-toggle");
  let loaded = false;
  function toggle() {
    const nowCollapsed = panel.classList.toggle("collapsed");
    toggleBtn.setAttribute("aria-expanded", String(!nowCollapsed));
    panel.querySelector(".dl-chevron").textContent = nowCollapsed ? "▸" : "▾";
    if (!nowCollapsed && !loaded) { loaded = true; refresh(); }
  }
  toggleBtn.addEventListener("click", toggle);

  async function refresh() {
    body.innerHTML = `<div class="dl-empty">loading…</div>`;
    const data = await ledgerRefusals(30);
    if (!data) {
      body.innerHTML = `<div class="dl-empty">no dev ledger (set MRE_DEV)</div>`;
      return;
    }
    const clusters = data.clusters || [];
    if (!clusters.length) {
      body.innerHTML = `<div class="dl-empty">no refusals logged yet</div>`;
      return;
    }
    body.innerHTML = "";
    for (const c of clusters) {
      const row = document.createElement("div");
      row.className = "dl-row";
      const flag = c.any_rephrased ? ` <span class="dl-fixed" title="a later rephrase succeeded">↳ rephrased</span>` : "";
      row.innerHTML =
        `<span class="dl-count">${c.count}×</span>` +
        `<span class="dl-q"></span>` +
        `<span class="dl-route">${c.route}</span>${flag}`;
      row.querySelector(".dl-q").textContent = c.example;
      body.appendChild(row);
    }
  }

  panel.querySelector(".dl-refresh").addEventListener("click", (e) => {
    e.stopPropagation();
    loaded = true;
    refresh();
  });
  // Deferred: the body loads on first expand (start collapsed → no eager fetch).
  return { refresh, toggle, el: panel };
}
