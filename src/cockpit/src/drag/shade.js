// Tier-0 shading (CU1, R-DP2/R-DP6). On grab, paint each resource row with the
// legality map for the grabbed op:
//   * ineligible row (capability)     → a strong DIM wash across the row
//   * eligible row                    → a faint dim wash, GREEN bands over the
//                                       legal start regions, AMBER bands over
//                                       occupied spans (fit-but-displace: still
//                                       legal, just not free)
// Green = provably-not-illegal by the cheap rules; dim = proven illegal. The
// conservative-error direction (R-DP6) is tier0.js's; this only paints what it
// computed. Drawn into the shade layer in px via geometry; re-called on every
// pan/zoom so it tracks the board (the C1 discipline).
//
// Pure-ish: it writes DOM into a provided layer element from a Tier-0 result +
// geometry + the board window. No state of its own.

const ms = (iso) => Date.parse(iso);

export function renderShade(layerEl, tier0, geometry, win) {
  layerEl.replaceChildren();
  const winStart = ms(win.start), winEnd = ms(win.end);

  for (const row of tier0.rows) {
    const band = geometry.rowBand(row.resource_id);
    if (!band) continue;

    // full-row wash (dim strength differs eligible vs capability-dim). The dim
    // reason is the row's own (capability / no_calendar_window / wip_fixed) so
    // the hover reads the truth (contract 1.4, R-DP6 / Session 4.0b).
    const wash = document.createElement("div");
    wash.className = row.eligible ? "shade-row eligible" : "shade-row dim capability";
    wash.dataset.reason = row.eligible ? "" : (row.reason || "capability");
    Object.assign(wash.style, {
      left: "0px", right: "0px",
      top: `${band.top}px`, height: `${band.height}px`,
    });
    layerEl.appendChild(wash);
    if (!row.eligible) continue;

    // green legal-start regions
    for (const r of row.legal_regions) {
      const seg = _seg(geometry, row.resource_id, ms(r.start), ms(r.end), winStart, winEnd, band);
      if (!seg) continue;
      const el = document.createElement("div");
      el.className = "shade-seg green";
      Object.assign(el.style, seg);
      layerEl.appendChild(el);
    }
    // amber occupancy (fit-but-displace)
    for (const o of row.occupied || []) {
      const seg = _seg(geometry, row.resource_id, ms(o.start), ms(o.end), winStart, winEnd, band);
      if (!seg) continue;
      const el = document.createElement("div");
      el.className = "shade-seg amber";
      Object.assign(el.style, seg);
      layerEl.appendChild(el);
    }
  }
}

// clip [s,e] to the visible window, convert to a positioned px rect on the row.
function _seg(geometry, rid, s, e, winStart, winEnd, band) {
  const a = Math.max(s, winStart), b = Math.min(e, winEnd);
  if (a >= b) return null;
  const x0 = geometry.timeToX(a), x1 = geometry.timeToX(b);
  if (x0 == null || x1 == null) return null;
  return { left: `${x0}px`, width: `${Math.max(1, x1 - x0)}px`,
           top: `${band.top}px`, height: `${band.height}px` };
}
