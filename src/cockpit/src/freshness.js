// Schedule-freshness detection (Session 4.3 CU6, rescoped Session 4.4 CU1).
// PURE, framework-free. A bound schedule can be perfectly valid (NOT superseded)
// yet simply STALE — a newer solve exists in the registry while a tab sits on an
// old one. The product must notice, and never leave the user unknowingly on
// anything but the newest relevant schedule.
//
// SCOPE (4.4 CU1 — the sixth stale-tab incident): the original 4.3 rule compared
// only against the SAME SUBMISSION, which was proven blind to the RESUBMIT
// workflow — a planner who fixes data in Excel and re-submits mints a NEW
// submission id, so its newer solve was never offered. "Relevant" for the
// dev/single-tenant deployment is therefore the whole DATA ROOT: the newest LIVE
// (non-superseded) schedule strictly newer than the bound one, regardless of
// submission. Multi-tenant scoping (a tenant boundary the root does not model) is
// a future concern — see docs/04 2026-07-19 — deliberately NOT pre-built here.
//
// The listing (GET /schedules) is ordered oldest→newest by created_at and never
// includes what-if scenarios (evidence isolation), so a "newer" schedule is any
// non-superseded row AFTER the bound one in that order.
//
// "Strictly newer" is by created_at when the rows carry it (the real listing
// always does — ORDER BY created_at) and by list position otherwise (a fixture
// row without a timestamp). Equal created_at is NOT newer: two live schedules
// minted at the same instant are not a progression of one another, so a tie never
// yanks the tab (this is what keeps unrelated demo fixtures from cross-following).
//
// Returns the id of the newest live schedule strictly newer than the bound one,
// or null (bound is already newest / bound absent / empty listing).
export function findNewerSchedule(boundId, schedules) {
  if (!Array.isArray(schedules) || !schedules.length) return null;
  const boundIdx = schedules.findIndex((s) => s && s.id === boundId);
  if (boundIdx < 0) return null;                  // bound not in the live listing
  const bound = schedules[boundIdx];
  const boundT = bound.created_at ? Date.parse(bound.created_at) : null;
  let best = null;
  let bestKey = null;
  schedules.forEach((s, i) => {
    if (!s || !s.id || s.id === boundId) return;
    if (s.status === "superseded") return;             // never route to a dead version
    if (s.is_scenario) return;                          // belt-and-suspenders (already excluded)
    const t = s.created_at ? Date.parse(s.created_at) : null;
    const newer = (boundT != null && t != null) ? t > boundT : i > boundIdx;
    if (!newer) return;
    const key = t != null ? t : i;                      // rank by time, else position
    if (bestKey == null || key >= bestKey) { best = s.id; bestKey = key; }
  });
  return best;
}
