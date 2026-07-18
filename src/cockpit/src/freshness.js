// Newer-schedule detection (Session 4.3 CU6) — PURE, framework-free. Extends the
// 3.8 superseded self-heal: a bound schedule can be perfectly valid (NOT
// superseded) yet simply STALE — a newer solve of the same submission exists in
// the registry while a tab sits on an old one. The product should notice.
//
// The listing (GET /schedules) is ordered oldest→newest by created_at and never
// includes what-if scenarios (evidence isolation). "Same scope" = the same
// SUBMISSION: a newer schedule of a DIFFERENT submission is a different plan, not
// a newer version of this one, so it is never offered. When the submission is
// unknown (a fixture row without submission_id), we never guess.
//
// Returns the id of the newest live same-submission schedule strictly newer than
// the bound one, or null.
export function findNewerSchedule(boundId, schedules) {
  if (!Array.isArray(schedules) || !schedules.length) return null;
  const idx = schedules.findIndex((s) => s && s.id === boundId);
  if (idx < 0) return null;                       // bound not in the live listing
  const sub = schedules[idx].submission_id ?? null;
  if (sub == null) return null;                   // unknown scope → never guess
  let newer = null;
  for (let i = idx + 1; i < schedules.length; i++) {  // AFTER = newer (created_at asc)
    const s = schedules[i];
    if (!s || s.status === "superseded") continue;      // never route to a dead version
    if ((s.submission_id ?? null) !== sub) continue;    // SAME submission scope only
    newer = s.id;                                       // keep the last (newest)
  }
  return newer;
}
