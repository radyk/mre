// Capacity-state banding for a Gantt row (docs/07 Session 4.2 CU1). PURE.
//
// Turns a row's flattened calendar windows + its occupancy into the coloured
// background bands the board shades — each provably-sourced from the model, no
// unplanned/observed downtime invented (that has no doorway yet; docs/04 4.2):
//
//   offshift    time in the span that is NO window at all (nights / weekends)
//   closure     a calendar closure exception (holiday / breakdown / generic)
//   maintenance a closure exception whose reason is planned_maintenance
//   overtime    a premium (added-capacity) window — the Phase-1 overtime machinery
//   openidle    regular capacity with no work booked on it (idle open time)
//
// Booked regular time is NOT banded — the assignment bar itself covers it.
import { mergeWindows } from "./rowstats.js";

const ms = (iso) => Date.parse(iso);

// A \ B for sorted, merged interval lists (all [start,end] ms).
function subtract(a, b) {
  const out = [];
  const B = mergeWindows(b.map((w) => [w[0], w[1]]));
  for (let [s, e] of mergeWindows(a.map((w) => [w[0], w[1]]))) {
    let cur = s;
    for (const [bs, be] of B) {
      if (be <= cur || bs >= e) continue;
      if (bs > cur) out.push([cur, Math.min(bs, e)]);
      cur = Math.max(cur, be);
      if (cur >= e) break;
    }
    if (cur < e) out.push([cur, e]);
  }
  return out.filter(([x, y]) => y > x);
}

// windows: resources[i].calendar_windows (each {start,end,kind,reason?}).
// occupancy: [{start,end}] ms for this row's bars.
// span: {start,end} ms — the extent to band off-shift across (the doc horizon).
// Returns [{kind, start, end}] ms bands (kind ∈ offshift/closure/maintenance/
// overtime/openidle).
export function capacityBands(windows, occupancy, span) {
  const reg = [], ot = [], closures = [];
  for (const w of windows || []) {
    const iv = [ms(w.start), ms(w.end)];
    if (w.kind === "regular") reg.push(iv);
    else if (w.kind === "overtime") ot.push(iv);
    else if (w.kind === "closure") closures.push({ iv, reason: w.reason || null });
  }
  const occ = (occupancy || []).map((o) => [o.start, o.end]);
  const closureIvs = closures.map((c) => c.iv);

  const bands = [];
  const push = (kind, list) => { for (const [s, e] of list) if (e > s) bands.push({ kind, start: s, end: e }); };

  // open-idle = regular capacity minus booked work.
  push("openidle", subtract(reg, occ));
  // overtime windows (premium) rendered whole.
  push("overtime", ot);
  // closures, split by reason (planned maintenance called out).
  for (const c of closures) {
    const kind = c.reason === "planned_maintenance" ? "maintenance" : "closure";
    if (c.iv[1] > c.iv[0]) bands.push({ kind, start: c.iv[0], end: c.iv[1] });
  }
  // off-shift = the span minus every declared window (regular ∪ overtime ∪ closure).
  const declared = [...reg, ...ot, ...closureIvs];
  push("offshift", subtract([[span.start, span.end]], declared));

  bands.sort((a, b) => a.start - b.start || a.kind.localeCompare(b.kind));
  return bands;
}

// Shift-boundary instants (ms) within [from,to]: the start and end of each
// regular window — the "subtle ticks" the markers overlay draws. Deduped/sorted.
export function shiftBoundaries(windows, from, to) {
  const set = new Set();
  for (const w of windows || []) {
    if (w.kind !== "regular") continue;
    const s = ms(w.start), e = ms(w.end);
    if (s >= from && s <= to) set.add(s);
    if (e >= from && e <= to) set.add(e);
  }
  return [...set].sort((a, b) => a - b);
}
