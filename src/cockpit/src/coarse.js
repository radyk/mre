// THE COARSE ZONE's DENSITY BAND (Session 4B.6 CU5, R-SC2 coarse-zone amendment).
//
// CLAUSE (6) — COARSE NEVER RENDERS AS A BAR. Bars mean placement: a bar says
// "this operation runs on this machine from 09:14 to 11:40", and the board's
// whole grammar rests on that promise. Coarse output is not a placement. It is
// LOAD — how many minutes of known future work want a machine-week, against how
// many minutes that machine-week has. Different epistemic status, different
// visual grammar: a density band, gridded by resource x bucket, never on the
// timeline and never draggable.
//
// Every cell states its own arithmetic in its tooltip (load / capacity), because
// the colour is a summary and the numbers are the fact. Nothing here converts a
// bucket into currency (clause 5) and nothing says "scheduled".
//
// Read-only: renders from doc.rolling.coarse_zone; touches no state.

const clamp01 = (x) => (x < 0 ? 0 : x > 1 ? 1 : x);

const fmtBucket = (b, bucketDays) => {
  const d = new Date(b.start);
  if (Number.isNaN(d.getTime())) return `#${b.index}`;
  const label = d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  return bucketDays === 7 ? label : `${label}+${bucketDays}d`;
};

// The provenance sentence. CLAUSE (3): a DEFAULTED derate must never read as
// the plant's own choice, so the band says which it is, every time.
function derateNote(cz) {
  const pct = `${Math.round(cz.capacity_derate * 100)}%`;
  if (cz.capacity_derate_provenance === "declared") {
    return cz.capacity_derate >= 1
      ? "capacity: full calendar (declared derate 1.0)"
      : `capacity: ${pct} of calendar — your declared planning derate`;
  }
  return cz.capacity_derate >= 1
    ? "capacity: full calendar — no derate declared, nothing shaved off"
    : `capacity: ${pct} of calendar — a default, not declared by this plant`;
}

export function mountCoarseBand(hostEl, doc) {
  const rolling = doc && doc.rolling;
  const cz = rolling && rolling.coarse_zone;
  if (!cz) return null; // the coarse zone did not run: render nothing, claim nothing

  const buckets = cz.buckets || [];
  const cells = cz.density || [];
  const byRes = new Map();
  for (const c of cells) {
    if (!byRes.has(c.resource_id)) byRes.set(c.resource_id, new Map());
    byRes.get(c.resource_id).set(c.bucket_index, c);
  }
  // busiest first, so the thing a planner needs is at the top
  const rows = [...byRes.entries()].sort((a, b) => {
    const peak = (m) => Math.max(0, ...[...m.values()].map((c) => c.utilization));
    return peak(b[1]) - peak(a[1]);
  });

  const el = document.createElement("div");
  el.className = "coarse-band";
  el.id = "coarse-band";

  const head = document.createElement("div");
  head.className = "cb-head";
  const title = document.createElement("span");
  title.className = "cb-title";
  title.textContent = "Coarse look-ahead — load, not placement";
  const note = document.createElement("span");
  note.className = "cb-note";
  note.textContent = derateNote(cz);
  head.append(title, note);
  // An UPPER-BOUND or truncated run must say so on the surface, not only in an
  // answer the planner has to ask for.
  if (cz.figures_are_upper_bounds || cz.wall_truncated) {
    const warn = document.createElement("span");
    warn.className = "cb-warn";
    warn.textContent = cz.wall_truncated
      ? "incomplete search — figures are not reproducible"
      : "upper bound — the search did not prove an optimum";
    head.appendChild(warn);
  }
  if (cz.infeasibility_proven) {
    const proof = document.createElement("span");
    proof.className = "cb-proof";
    proof.textContent = "proven: this cannot fit at full capacity";
    head.appendChild(proof);
  }
  el.appendChild(head);

  const grid = document.createElement("div");
  grid.className = "cb-grid";
  grid.style.setProperty("--cb-cols", String(buckets.length));

  // column header: the bucket starts
  const corner = document.createElement("div");
  corner.className = "cb-corner";
  grid.appendChild(corner);
  for (const b of buckets) {
    const h = document.createElement("div");
    h.className = "cb-colhead";
    h.textContent = fmtBucket(b, cz.bucket_days);
    h.title = `${b.start.slice(0, 10)} to ${b.end.slice(0, 10)}`;
    grid.appendChild(h);
  }

  for (const [resId, m] of rows) {
    const label = document.createElement("div");
    label.className = "cb-rowhead";
    label.textContent = resId.length > 14 ? `${resId.slice(0, 13)}…` : resId;
    label.title = resId;
    grid.appendChild(label);
    for (const b of buckets) {
      const c = m.get(b.index);
      const cell = document.createElement("div");
      cell.className = "cb-cell";
      const u = c ? clamp01(c.utilization) : 0;
      cell.style.setProperty("--cb-u", u.toFixed(3));
      if (c && c.utilization >= 0.95) cell.classList.add("cb-hot");
      if (!c) cell.classList.add("cb-idle");
      cell.dataset.res = resId;
      cell.dataset.bucket = String(b.index);
      cell.dataset.util = c ? String(c.utilization) : "0";
      // the arithmetic, never just the colour
      cell.title = c
        ? `${resId} · week of ${b.start.slice(0, 10)}\n`
          + `${c.load_minutes} min of work against ${c.capacity_minutes} min `
          + `of capacity (${Math.round(c.utilization * 100)}%)\n`
          + "a load estimate over whole weeks — not a placement"
        : `${resId} · week of ${b.start.slice(0, 10)}\nno coarse load`;
      grid.appendChild(cell);
    }
  }
  el.appendChild(grid);

  if (cz.unmodelable_count > 0) {
    const foot = document.createElement("div");
    foot.className = "cb-foot";
    foot.textContent =
      `${cz.unmodelable_count} operation${cz.unmodelable_count === 1 ? "" : "s"} `
      + `left out — the coarse model cannot represent `
      + `${cz.unmodelable_count === 1 ? "it" : "them"}, so this picture is incomplete`;
    el.appendChild(foot);
  }

  hostEl.appendChild(el);
  return {
    el,
    // harness probe: what the band actually rendered, in numbers.
    probe() {
      const cellEls = [...el.querySelectorAll(".cb-cell")];
      return {
        buckets: buckets.length,
        resources: rows.length,
        cells: cellEls.length,
        hot: cellEls.filter((c) => c.classList.contains("cb-hot")).length,
        derateProvenance: cz.capacity_derate_provenance,
        infeasibilityProven: !!cz.infeasibility_proven,
        // CLAUSE (6): the band must never emit a bar element.
        bars: el.querySelectorAll(".bar, .vis-item").length,
      };
    },
  };
}
