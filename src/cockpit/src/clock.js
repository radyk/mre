// THE ONE CLOCK (R-TZ1, docs/04 2026-08-03; Session 4B.35).
//
// Every planner-facing time in this cockpit renders in ONE declared clock — the
// FACILITY's, from the IDS manifest (docs/06 §3), delivered on /meta with its
// provenance. Nothing here changes what is STORED: instants are UTC on the wire
// and UTC in the document. This module is the rendering boundary, and it is the
// only one: a `toLocaleString` anywhere else in the cockpit is a second clock,
// which is the defect this file exists to end.
//
// WHY IT MATTERED (4B.35 §2). The board and job panel rendered through
// `toLocaleString(undefined, …)` — the BROWSER's zone — while the ask path's
// testimony rendered the stored UTC verbatim. On the Khalil board, in Toronto in
// January, that is exactly five hours: the panel said ORD-000128 op20 ran
// "11:09 → 13:29" and the testimony said it finished at "18:29". Both were
// derived correctly from the same instant. Neither said which clock it was in,
// so the pair read as a contradiction — and a planner cannot audit a schedule
// whose two surfaces disagree about when the work happens.
//
// The zone is applied through `Intl.DateTimeFormat`'s `timeZone`, which resolves
// IANA zones including their DST transitions — so this is exact for a named
// facility zone, not a fixed-offset approximation.

const FALLBACK = { timezone: "UTC", provenance: "defaulted",
                   label: "All times UTC · assumed" };

let _clock = FALLBACK;

// Set ONCE at boot from /meta. Callers that render before the meta read (there
// are none today) get the fallback, which is UTC — the clock the instants are
// already in, so an early render is never in a third clock.
export function initClock(meta) {
  const c = meta && meta.clock;
  _clock = (c && typeof c.timezone === "string" && c.timezone)
    ? { timezone: c.timezone,
        provenance: c.provenance || "declared",
        label: c.label || `All times ${c.timezone}` }
    : FALLBACK;
  return _clock;
}

export const clockZone = () => _clock.timezone;
export const clockLabel = () => _clock.label;
export const clockProvenance = () => _clock.provenance;

const EM_DASH = "—";
const parse = (v) => (v instanceof Date ? v : new Date(v));

// Cache formatters: a drag redraws these hundreds of times per second, and
// constructing an Intl.DateTimeFormat is not cheap.
const _fmts = new Map();
function formatter(opts) {
  const key = clockZone() + "|" + JSON.stringify(opts);
  let f = _fmts.get(key);
  if (!f) {
    f = new Intl.DateTimeFormat("en-CA", { ...opts, timeZone: clockZone() });
    _fmts.set(key, f);
  }
  return f;
}

// The one formatting entry point. `opts` is an Intl.DateTimeFormat option bag
// WITHOUT a timeZone — supplying one here would be a second clock, so it is
// stripped. Returns an em dash for a null/unparseable instant, exactly as the
// call sites it replaces did.
export function fmt(value, opts) {
  if (value == null) return EM_DASH;
  const d = parse(value);
  if (Number.isNaN(d.getTime())) return EM_DASH;
  const { timeZone, ...rest } = opts || {};   // eslint-disable-line no-unused-vars
  return formatter(rest).format(d);
}

// The common shapes, named so call sites read as intent rather than as an
// option bag. Each mirrors the option bag the site used before R-TZ1.
export const fmtDateTime = (v) => fmt(v, {
  month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
export const fmtDate = (v) => fmt(v, { month: "short", day: "numeric" });
export const fmtTime = (v) => fmt(v, { hour: "2-digit", minute: "2-digit" });
export const fmtWeekdayTime = (v) => fmt(v, {
  weekday: "short", hour: "2-digit", minute: "2-digit" });
export const fmtFull = (v) => fmt(v, {
  year: "numeric", month: "short", day: "numeric",
  hour: "2-digit", minute: "2-digit" });

// The declared clock's UTC offset (MINUTES, east-positive) at a given instant.
// Computed per-instant rather than once, so a zone with DST is exact on both
// sides of a transition inside one view. Used to drive vis-timeline's axis.
export function offsetMinutesAt(value) {
  const d = parse(value);
  if (Number.isNaN(d.getTime())) return 0;
  // Format the instant in the target zone, read it back as if UTC, and take the
  // difference. This is the standard Intl offset derivation and needs no
  // timezone database of our own.
  const p = formatter({
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  }).formatToParts(d).reduce((a, x) => (a[x.type] = x.value, a), {});
  const asUTC = Date.UTC(+p.year, +p.month - 1, +p.day,
                         +p.hour % 24, +p.minute, +p.second);
  return Math.round((asUTC - d.getTime()) / 60000);
}
