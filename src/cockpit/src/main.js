// Cockpit entry point (docs/07 Phase 3 interim-A). Resolves the schedule,
// fetches its contract-1.2 document + certificate grade, renders the board and
// the ask panel, and paints the top strip (version + grade). Read-only.
import "./cockpit.css";
import {
  CONFIG, ApiError, resolveScheduleId, getSchedule, getScheduleMeta,
  resolveSuccessor, listSchedules,
} from "./api.js";
import { mountSchedulePicker, renderScheduleList } from "./schedulepicker.js";
import { createBoard } from "./board.js";
import { createAskPanel } from "./askpanel.js";
import { wireInteraction } from "./interaction.js";
import { mountDevLedger } from "./devledger.js";
import { findNewerSchedule } from "./freshness.js";
import { mountTray } from "./tray.js";
import { mountCoarseBand } from "./coarse.js";

// Rewrite the address bar to bind the given schedule version WITHOUT a reload
// (session 3.8 CU1): a live accept/publish stays in the same session, but the
// URL must name the version the board IS, so a reload never re-binds a
// now-superseded id. Other query params (api, ask) are preserved.
function setUrlSchedule(id) {
  const url = new URL(location.href);
  url.searchParams.set("schedule", id);
  history.replaceState(null, "", url);
}

// Navigate the cockpit to a different version with a full reload (session 3.8
// CU3): used for "view current" on a superseded deep link and for the live 409
// self-heal — a clean reload guarantees fresh board/interaction/ask state bound
// to the successor, never a half-rebound zombie.
function jumpToVersion(id) {
  const url = new URL(location.href);
  url.searchParams.set("schedule", id);
  location.assign(url.toString());
}

const GRADE_CLASS = {
  ACCEPTED: "g-c1", CONDITIONAL: "g-conditional", REJECTED: "g-rejected",
  C1: "g-c1", C2: "g-c2", C3: "g-c3", C0: "g-c0",
};

// Theme (Session 4.1): light is the shipped default; dark is an option. The
// attribute is stamped pre-paint by the head script in index.html (no flash);
// here we keep it in sync with the URL + localStorage and expose a chrome
// toggle. Theme choice is a tier-2-class preference — a per-deployment default
// when that layer lands; a URL/config param + this toggle for now.
function currentTheme() {
  return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
}
function paintThemeToggle(btn, theme) {
  const to = theme === "dark" ? "light" : "dark";
  btn.textContent = theme === "dark" ? "☾ dark" : "☀ light";
  btn.title = `switch to ${to} theme`;
  btn.setAttribute("aria-label", `theme: ${theme}. switch to ${to}`);
}
function applyTheme(t) {
  const theme = t === "dark" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", theme);
  try { localStorage.setItem("mre-theme", theme); } catch { /* private mode */ }
  const url = new URL(location.href);
  url.searchParams.set("theme", theme);
  history.replaceState(null, "", url);
  const btn = document.getElementById("theme-toggle");
  if (btn) paintThemeToggle(btn, theme);
  if (window.__cockpit) window.__cockpit.theme = theme;
  return theme;
}
function toggleTheme() { return applyTheme(currentTheme() === "dark" ? "light" : "dark"); }

// A HUMAN-SCALE schedule identity (Session 4.4 CU3): the hex alone was proven
// insufficient across six stale-tab incidents — two visually-similar boards read
// identically. The registry carries a generation counter + a created_at, so the
// strip shows "solve #3 · 09:41". Falls back to the short hex when the registry
// pre-dates these fields (a plain document, a pool member) — never a blank.
function scheduleIdentity(doc, meta) {
  const shortId = (doc.schedule_id || "").slice(0, 8);
  const gen = meta && meta.generation;
  let clock = null;
  if (meta && meta.created_at) {
    const t = new Date(meta.created_at);
    if (!Number.isNaN(t.getTime())) {
      clock = t.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
  }
  if (gen && clock) return { label: `solve #${gen} · ${clock}`, title: shortId };
  if (gen) return { label: `solve #${gen}`, title: shortId };
  if (clock) return { label: `${shortId} · ${clock}`, title: shortId };
  return { label: shortId, title: shortId };
}

// THE COST PROOF CHIP (Session 4B.11 CU1 — docs/07 §5a.23).
//
// A schedule whose cost is provably optimal SAYS SO; one that is not says that,
// with its gap. This is not decoration: 4B.10 measured five runs of one instance
// differing only in the solver's random seed splitting 4 OPTIMAL / 1 FEASIBLE,
// the unproved run's ledger 13.056% dearer than the optimum the other four prove
// to the cent — and `solver.status` was the ONLY thing distinguishing them,
// rendered nowhere. It sits in the strip beside the certificate grade, not in a
// diagnostics drawer, because it qualifies every number on the board.
//
// The label and title are composed SERVER-SIDE (mre.modules.cost_proof) and
// arrive on /meta. Nothing here composes wording, so the chip and the ask
// panel's rider cannot state different things about the same solve. No proof on
// meta -> no chip: an absent verdict is never guessed.
function costProofChip(meta) {
  const p = meta && meta.cost_proof;
  if (!p || !p.label) return "";
  const cls = `proof-${p.state || "none"}`;
  return `<span class="costproof ${cls}" title="${escapeAttr(p.title || "")}">`
       + `<span class="lbl">cost</span> ${escapeHtml(p.label)}</span>`;
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
const escapeAttr = escapeHtml;

// Session 4B.13 Item 5(b) — the feel tuning panel's SECOND gate. A dev build is
// necessary but no longer sufficient: the panel is off unless asked for.
// sessionStorage, not localStorage, matching the convention already used for
// per-tab decisions in this file — a new tab is a new decision, so a stray
// `?feel=1` never follows the product into a demo.
function feelTuningEnabled() {
  try {
    const q = new URL(window.location.href).searchParams.get("feel");
    if (q !== null) {
      const on = q !== "0" && q !== "false";
      sessionStorage.setItem("mre-feel-tuning", on ? "1" : "0");
      return on;
    }
    return sessionStorage.getItem("mre-feel-tuning") === "1";
  } catch {            // private mode / no storage — default OFF, never on
    return false;
  }
}

function paintTopStrip(el, doc, meta) {
  const grade = meta?.grade || "—";
  const costing = meta?.costing_grade ? ` / ${meta.costing_grade}` : "";
  const gcls = GRADE_CLASS[(meta?.grade || "").toUpperCase()] || "g-c0";
  const ident = scheduleIdentity(doc, meta);
  el.innerHTML = `
    <span class="brand">Reasoning Cockpit</span>
    <span class="ver" title="${ident.title}">contract ${doc.contract_version} · <button type="button" class="sched-ident" id="sched-ident">${ident.label}<span class="sched-caret" aria-hidden="true">▾</span></button></span>
    <span class="status">${doc.status}</span>
    ${costProofChip(meta)}
    <span class="grade ${gcls}"><span class="lbl">certificate</span> ${grade}${costing}</span>
    <button class="theme-toggle" id="theme-toggle"></button>`;
  // the toggle is recreated on every repaint (version change too) — (re)bind it.
  const btn = el.querySelector("#theme-toggle");
  paintThemeToggle(btn, currentTheme());
  btn.addEventListener("click", toggleTheme);
  // Hotfix CU2: the identity chip is the schedule switcher. Recreated on every
  // repaint like the toggle, so it is (re)mounted here. The bound id is resolved
  // AT OPEN TIME (a live accept rebinds without a reload), and a pick is a full
  // navigation — the URL becomes the chosen id.
  const identBtn = el.querySelector("#sched-ident");
  identBtn.title = "switch schedule";
  const picker = mountSchedulePicker(identBtn, {
    currentId: () => (window.__cockpit && window.__cockpit.scheduleId) || doc.schedule_id,
    load: listSchedules,
    onPick: (id) => {
      const bound = (window.__cockpit && window.__cockpit.scheduleId) || doc.schedule_id;
      if (id && id !== bound) jumpToVersion(id);
    },
  });
  if (window.__cockpit) window.__cockpit.picker = picker;
  return picker;
}

// CU1 — the honest floor for an explicit ?schedule= naming an id this data root
// does not have. It NAMES the id (a silent substitution is what sent the founder
// to a different board), states that nothing was loaded in its place, and offers
// the registered schedules as the recovery — the same list the header picker
// serves. The listing may itself be down; that renders its own honest line.
async function scheduleNotFound(app, strip, id) {
  app.querySelector(".split")?.remove();
  // the strip's boot placeholder says "loading…" — leaving it there would claim
  // work is still in flight when it has already failed.
  strip.innerHTML = `<span class="brand">Reasoning Cockpit</span>`
    + `<span class="status">no schedule</span>`;
  const el = document.createElement("div");
  el.className = "err notfound";
  el.id = "schedule-not-found";
  const head = document.createElement("div");
  head.className = "nf-head";
  head.append("no schedule ");
  const code = document.createElement("code");
  code.className = "nf-id";
  code.textContent = id;                 // straight from the URL — never innerHTML
  head.append(code, " in this data root");
  const sub = document.createElement("div");
  sub.className = "nf-sub";
  sub.textContent = "Nothing was loaded in its place. Pick a registered schedule:";
  el.append(head, sub);
  app.appendChild(el);

  let schedules = [];
  try { ({ schedules } = await listSchedules()); } catch { schedules = []; }
  el.appendChild(renderScheduleList(schedules, {
    currentId: null,
    onPick: jumpToVersion,
    emptyText: "no schedules registered — solve one first (POST /submissions/{id}/solve)",
  }));
  window.__cockpit = {
    ready: true,
    error: `unknown schedule ${id}`,
    notFound: id,
    scheduleId: null,
    schedules: schedules || [],
  };
}

// A read-only banner shown when the loaded schedule has been superseded
// (session 3.8 CU3): planner language + a one-click jump to the current
// version, never a raw "superseded" error and never an editable zombie board.
function supersededBanner(hostEl, successorId) {
  const el = document.createElement("div");
  el.className = "superseded-banner";
  el.id = "superseded-banner";
  const shortSucc = successorId ? successorId.slice(0, 8) : null;
  el.innerHTML = shortSucc
    ? `<span class="sb-msg">This plan was replaced by a newer version.</span>
       <button class="sb-jump" id="sb-jump">View current (${shortSucc}) →</button>
       <span class="sb-ro">read-only</span>`
    : `<span class="sb-msg">This plan has been superseded and is read-only.</span>
       <span class="sb-ro">read-only</span>`;
  hostEl.prepend(el);
  if (successorId) {
    el.querySelector("#sb-jump").addEventListener("click", () => jumpToVersion(successorId));
  }
  return el;
}

// The board chrome row (Session 4.3 CU1/CU5): the legend (left) + a right cluster
// holding a first-load "Ctrl+scroll to zoom" hint, the +/− zoom controls, and
// (dev only) the question-ledger dock. ONE structural row, so nothing floats over
// the legend or the ask column at any width (the SECOND occlusion incident). The
// legend is visible by default on first load (CU4). Returns { chrome, right } —
// the dev ledger docks into `right`.
function mountBoardChrome(boardHost, board) {
  const host = boardHost.parentElement;            // .board-host (position: relative)
  const chrome = document.createElement("div");
  chrome.className = "board-chrome";

  const lg = document.createElement("div");
  lg.className = "legend";
  // Two groups: the lateness signal on the bars, and the capacity-state
  // backgrounds (Session 4.2 CU1). A hatched swatch marks the hatched bands.
  lg.innerHTML = `
    <span><span class="sw" style="background: var(--bar-ontime)"></span>on time / early</span>
    <span><span class="sw" style="background: var(--bar-tight)"></span>tight</span>
    <span><span class="sw" style="background: var(--bar-late)"></span>late</span>
    <span class="lg-gap"></span>
    <span><span class="sw" style="background: var(--cap-offshift)"></span>off shift</span>
    <span><span class="sw sw-hatch-closure"></span>closure</span>
    <span><span class="sw sw-hatch-maint"></span>maintenance</span>
    <span><span class="sw" style="background: var(--cap-overtime); border:1px solid var(--standing-pin-edge)"></span>overtime</span>
    <span><span class="sw" style="background: var(--cap-openidle)"></span>open · idle</span>
    <span class="lg-gap"></span>
    <span><span class="sw sw-now"></span>now</span>
    <span><span class="sw" style="background: var(--cite-bar)"></span>cited</span>`;
  chrome.appendChild(lg);

  const right = document.createElement("div");
  right.className = "bc-right";

  // CU5: a first-load hint naming the trackpad-free zoom gesture; fades out so it
  // never becomes permanent chrome.
  const hint = document.createElement("div");
  hint.className = "board-hint";
  hint.id = "board-hint";
  hint.textContent = "Ctrl+scroll to zoom";
  right.appendChild(hint);
  setTimeout(() => hint.classList.add("fade"), 6000);
  setTimeout(() => { if (hint.isConnected) hint.remove(); }, 6600);

  // CU5: the +/− zoom controls (pointer/keyboard path; Ctrl+wheel unchanged).
  const zoom = document.createElement("div");
  zoom.className = "board-zoom";
  zoom.innerHTML = `
    <button type="button" class="bz-out" aria-label="zoom out" title="zoom out">−</button>
    <button type="button" class="bz-in" aria-label="zoom in" title="zoom in">+</button>`;
  zoom.querySelector(".bz-in").addEventListener("click", () => board.zoomIn());
  zoom.querySelector(".bz-out").addEventListener("click", () => board.zoomOut());
  right.appendChild(zoom);

  chrome.appendChild(right);
  host.appendChild(chrome);
  return { chrome, right };
}

// A dismissible "a newer schedule exists" info bar (Session 4.3 CU6): the bound
// version is valid but stale — a newer solve exists in the data root. One click
// jumps; a dismiss keeps the current view. Distinct from the superseded banner
// (that version is dead; this one is merely older). Shown ONLY when the planner
// has uncommitted state (Session 4.4 CU2) — an edit-in-flight, an open card, or a
// pinned conversation outranks freshness, so we let the user decide rather than
// auto-switch. With no such state the cockpit auto-follows instead (see below).
// Session 4B.5 CU4(a) — DISMISSAL IS STICKY, per offered id, per tab.
//
// The 4.4 dismiss handler removed the element and nothing else, and the watch's
// idempotence guard asked whether the banner was IN THE DOM. A dismissed banner
// therefore failed that guard on the very next check and was rebuilt — every 30
// seconds, and on every focus. Dismissing a notice has to mean something, and
// "this id, not again in this tab" is exactly what the planner said.
//
// sessionStorage, not localStorage: a NEW tab is a new decision. Private mode /
// storage-disabled degrades to the in-memory guard below, which still holds for
// the life of the page.
const DISMISSED_KEY = "mre-newer-dismissed";
function dismissedIds() {
  try {
    return new Set(JSON.parse(sessionStorage.getItem(DISMISSED_KEY) || "[]"));
  } catch { return new Set(); }
}
function rememberDismissed(id) {
  if (!id) return;
  try {
    const ids = dismissedIds();
    ids.add(id);
    sessionStorage.setItem(DISMISSED_KEY, JSON.stringify([...ids]));
  } catch { /* private mode — the in-memory guard still holds */ }
}

function newerBanner(hostEl, newId) {
  const el = document.createElement("div");
  el.className = "superseded-banner newer";
  el.id = "newer-banner";
  const short = (newId || "").slice(0, 8);
  el.innerHTML = `
    <span class="sb-msg">A newer schedule exists.</span>
    <button class="sb-jump" id="newer-jump">Open it (${short}) →</button>
    <button class="sb-dismiss" id="newer-dismiss" title="stay on this version">✕</button>`;
  hostEl.prepend(el);
  el.querySelector("#newer-jump").addEventListener("click", () => jumpToVersion(newId));
  el.querySelector("#newer-dismiss").addEventListener("click", () => {
    rememberDismissed(newId);        // CU4(a): dismissed means dismissed
    el.remove();
  });
  return el;
}

// Session 4.4 CU2 — the auto-follow toast. When the cockpit follows a newer
// schedule automatically (no uncommitted state), it reloads onto the new version;
// this brief, R-M1-legible toast then confirms the switch on the NEW page and
// offers a one-click way BACK to the previous version. The handoff across the
// reload rides sessionStorage (same tab, same origin) — set before the jump,
// read + cleared on the next boot.
const FOLLOW_KEY = "mre-followed-from";
function autoFollow(prevId, newId) {
  try { sessionStorage.setItem(FOLLOW_KEY, prevId); } catch { /* private mode */ }
  jumpToVersion(newId);
}
function followedToast(hostEl, prevId) {
  const el = document.createElement("div");
  el.className = "followed-toast";
  el.id = "followed-toast";
  const short = (prevId || "").slice(0, 8);
  el.innerHTML = `
    <span class="ft-msg">Switched to the new schedule.</span>
    <button class="ft-back" id="ft-back">View previous (${short}) →</button>`;
  hostEl.prepend(el);
  el.querySelector("#ft-back").addEventListener("click", () => {
    try { sessionStorage.removeItem(FOLLOW_KEY); } catch { /* ignore */ }
    jumpToVersion(prevId);   // going back is an explicit act — never re-followed
  });
  // fade out after a spell, but keep the "view previous" affordance reachable
  // until it does (R-M1: motion reads as a settle, not an alarm).
  setTimeout(() => el.classList.add("fade"), 7000);
  setTimeout(() => { if (el.isConnected) el.remove(); }, 7600);
  return el;
}

// The freshness watch (Session 4.4 CU2): re-checks the listing for a newer live
// schedule on window focus / tab re-show and on a slow poll, and — the exact
// moment a planner returns from Excel after a data fix — either FOLLOWS it (no
// uncommitted state) or offers the banner (uncommitted state present). Idempotent
// per newer id so a banner is never stacked; the auto-follow reload resets state.
// `pinned` (hotfix CU1) — the boot carried an explicit ?schedule=. That is an
// authoritative act: the tab was sent to THAT board on purpose (a deep link
// pasted from build_rolling_exam_run.py, a bookmark, a shared URL). A pinned tab
// is therefore NEVER auto-followed; it is OFFERED the newer schedule in the
// dismissible banner and the planner decides. This is the defect the founder hit:
// every `dev_cockpit.ps1` boot mints a busy_board solve into the shared _data
// root, so the boot-time check found a strictly-newer row and yanked the deep
// link to it before the board had settled (see CU3 in the closeout).
// `proposalLive` (Session 4B.23 Item 4) — THE POLL MAY NOT DISCARD A LIVE
// PROPOSAL. A dropped bar awaiting its verdict, and the delta card that follows
// it, are OPTIMISTIC CLIENT STATE: they exist nowhere in the persisted document,
// so there is nothing for a refresh to reconcile them against. Anything this
// watch does to the page while one is up can only destroy it — auto-follow is a
// full reload, and even the banner is PREPENDED into #app, which shortens the
// board host and moves the rows the proposal's absolutely-positioned overlay is
// pinned to.
//
// MECHANISM CHOSEN: SUPPRESS, not reconcile and not layer-above. Reconciling
// needs two versions of a placement and there is only one — the proposal is not
// in the document at all. Holding it above the poll means re-projecting overlay
// geometry after every reflow, which is machinery for a state that lasts
// seconds. Suppression is exact, and it costs nothing: the watch exists so a
// planner is not left on a stale board, which is not urgent inside a gesture,
// and the interval + focus listeners re-fire the moment the card closes — so
// the newer schedule is DEFERRED, never dropped.
//
// This is deliberately NARROWER than `hasUncommittedState`. A panel selection is
// uncommitted state too, and 4.4 CU2 rules that it gets the BANNER; that is
// unchanged. Only a live sandbox proposal defers the check entirely.
function installFreshnessWatch({ app, boundId, hasUncommittedState, pinned,
                                board, proposalLive }) {
  const offered = new Set();   // newer ids this tab has already surfaced, ever
  let inFlight = false;
  let deferrals = 0;           // how many checks a live proposal held back
  const currentBound = () => (window.__cockpit && window.__cockpit.scheduleId) || boundId;

  // CU4(b) — THE CHECK NEVER DISTURBS VIEWPORT STATE.
  //
  // WHAT WAS ACTUALLY FOUND, stated before the fix. The founder watched the
  // board's view reset on a re-check, and the mechanism is not subtle: on a tab
  // with no uncommitted state the check AUTO-FOLLOWS, which is a full page
  // reload, which resets everything. That is 4.4 CU2 working as designed — and it
  // fired constantly because `dev_cockpit.ps1` minted a fresh solve on every dev
  // restart, so there was always something newer to follow. CU4(e) removes the
  // supply (resuming is now the default); CU4(a)/(c) remove the second source,
  // where a dismissed banner failed the idempotence guard and was rebuilt every
  // thirty seconds, reflowing the board each time.
  //
  // What remains is this guard, and it is DEFENCE rather than the cure: the
  // banner is PREPENDED into #app, which shortens the board host, and a
  // background poll has no business moving what the planner is looking at. Any
  // DOM the watch inserts is wrapped — read the window before, put it back if the
  // reflow moved it. Selection and zoom ride on the same window, and nothing else
  // in this function touches the board.
  //
  // NAMED LIMIT: on the harness fixture the prepend does NOT move the window, so
  // the Playwright test for this is a standing invariant rather than a
  // reproduction of the founder's symptom. Said out loud because a green test
  // that never could have failed is worth exactly what it cost.
  function preserveViewport(mutate) {
    const before = board && board.getWindow ? board.getWindow() : null;
    mutate();
    if (!before || !board || !board.setWindow) return;
    requestAnimationFrame(() => {
      const after = board.getWindow();
      if (!after) return;
      const moved = String(after.start) !== String(before.start)
                 || String(after.end) !== String(before.end);
      if (moved) board.setWindow(before.start, before.end);
    });
  }

  const live = () => !!(proposalLive && proposalLive());

  async function check() {
    if (inFlight) return;
    // Item 4: a live proposal defers the WHOLE check — before the request…
    if (live()) { deferrals++; return; }
    inFlight = true;
    try {
      const { schedules } = await listSchedules();
      // …and again after it, because a drop can land while the listing is in
      // flight. The decision must be made against the state that exists NOW,
      // not the state that existed when the request was sent.
      if (live()) { deferrals++; return; }
      const id = currentBound();
      const newerId = findNewerSchedule(id, schedules || []);
      if (!newerId || newerId === id) return;
      if (pinned || hasUncommittedState()) {
        // an explicit ?schedule= or uncommitted state → never auto-switch; offer
        // the banner and leave the URL exactly as it was.
        //
        // CU4(c): ONE offer per newer id, then silence — the guard is what this
        // tab has OFFERED, not what is currently in the DOM. A tab that has
        // already been told is not told again on an interval, and (CU4(a)) a
        // dismissal survives the reload-free life of the tab.
        if (offered.has(newerId) || dismissedIds().has(newerId)) return;
        offered.add(newerId);
        preserveViewport(() => {
          document.getElementById("newer-banner")?.remove();
          newerBanner(app, newerId);
        });
        if (window.__cockpit) window.__cockpit.newerId = newerId;
      } else {
        autoFollow(id, newerId);   // clean slate → follow the newest, reload
      }
    } catch { /* background work; a listing failure never blocks the board */ }
    finally { inFlight = false; }
  }
  // Focus + visibility are the return-from-Excel signals; the interval is a slow
  // backstop for a tab left open in the foreground while a resubmit lands.
  window.addEventListener("focus", check);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") check();
  });
  const timer = setInterval(check, 30000);
  if (window.__cockpit) {
    window.__cockpit.checkFreshness = check;                  // harness seam
    // Item 4's probe: how many checks a live proposal held back. A test that
    // asserts "the board did not change" can also assert the watch RAN and
    // chose not to — otherwise a watch that was simply never called would pass.
    window.__cockpit.freshnessDeferrals = () => deferrals;
  }
  return { check, stop: () => clearInterval(timer), deferrals: () => deferrals };
}

async function boot() {
  const app = document.getElementById("app");
  const strip = document.getElementById("topstrip");
  const boardHost = document.getElementById("tl");
  const askRoot = document.getElementById("ask");
  try {
    // The URL param is authoritative over the head-script's early stamp, and
    // syncs it back to localStorage + the URL (Session 4.1).
    applyTheme(CONFIG.theme || currentTheme());
    // The auto-follow handoff (Session 4.4 CU2) is read FIRST, because it also
    // answers "was this ?schedule= put here by a human?" — see `pinned`.
    let followedFrom = null;
    try {
      followedFrom = sessionStorage.getItem(FOLLOW_KEY);
      if (followedFrom) sessionStorage.removeItem(FOLLOW_KEY);
    } catch { /* private mode */ }

    // Hotfix CU1: an explicit ?schedule= is AUTHORITATIVE. It picks the board
    // (resolveScheduleId already honors it), it is never rewritten to another id
    // by the app's own freshness resolution (see `pinned` below), and when the id
    // does not exist the cockpit says so by name instead of substituting.
    //
    // The ONE param the app writes itself is the landing of an auto-follow: 4.4
    // CU2 reloads onto the newer id, so that page's URL carries a param no human
    // typed. Treating it as pinned would end the follow chain after a single hop
    // — a tab that followed once would then only ever offer the banner. So an
    // auto-follow landing is explicitly NOT pinned, and the 4.4 story is intact.
    const pinned = !!CONFIG.scheduleId && !followedFrom;
    const id = await resolveScheduleId();
    let doc, meta;
    try {
      [doc, meta] = await Promise.all([getSchedule(id), getScheduleMeta(id)]);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        await scheduleNotFound(app, strip, id);
        return;
      }
      throw e;
    }
    // The URL must always name the version the board IS — even a deep link that
    // resolved via the listing (no ?schedule=) gets its id stamped in, so a
    // later live rebind + reload stay coherent (session 3.8 CU1). On a pinned
    // boot this is a no-op by construction: the id IS the param.
    setUrlSchedule(id);
    const picker = paintTopStrip(strip, doc, meta);
    // Session 4B.3a CU2: a rolling document docks a beyond-horizon tray below the
    // board — mark the host BEFORE createBoard so vis sizes the timeline to the
    // reduced height (board flex:1 + tray fixed) from the first frame.
    if (doc.rolling) boardHost.parentElement.classList.add("has-tray");
    // Session 4B.6 CU5: a rolling document that ran the COARSE ZONE docks a
    // density band under the tray. Clause (6) — coarse output is LOAD, never a
    // bar — so it is its own docked surface, not another timeline row.
    if (doc.rolling && doc.rolling.coarse_zone) {
      boardHost.parentElement.classList.add("has-coarse-band");
    }
    const board = createBoard(boardHost, doc);
    const chrome = mountBoardChrome(boardHost, board);
    // Session 4B.3a CU2(d): the beyond-horizon tray — a docked panel of known
    // future work with no bar to draw. Present only on a rolling document; a
    // monolithic board mounts nothing. Docked in the board-host, below the board.
    const tray = mountTray(boardHost.parentElement, doc);
    // Session 4B.6 CU5: the coarse zone's density band, below the tray. Returns
    // null (renders nothing, claims nothing) when the coarse zone did not run.
    const coarseBand = mountCoarseBand(boardHost.parentElement, doc);
    // Session 4B.3a CU2: on a rolling board, extend the legend with the sliced-
    // world vocabulary — the committed (locked) swatch + the frozen-boundary tick.
    if (doc.rolling) {
      const lg = chrome.chrome.querySelector(".legend");
      if (lg) {
        lg.insertAdjacentHTML("beforeend",
          `<span class="lg-gap"></span>`
          + `<span><span class="sw sw-committed"></span>committed</span>`
          + `<span><span class="sw sw-frozen"></span>frozen boundary</span>`);
      }

    }

    // A deep link to a SUPERSEDED version loads read-only behind a banner that
    // offers the current version (session 3.8 CU3) — never a raw error, never an
    // editable zombie. The gesture surface (which would 409 every drop against
    // reality) is deliberately NOT wired.
    const superseded = meta && meta.status === "superseded";

    // The live self-heal (session 3.8 CU3): any editing/asking call that 409s
    // "superseded" means a stale reference slipped through — resolve the live
    // successor and jump to it (a clean reload) rather than dead-ending.
    const onSuperseded = async (staleId) => {
      const succ = await resolveSuccessor(staleId || window.__cockpit.scheduleId);
      if (succ) jumpToVersion(succ);
      return succ;
    };

    // The dev build asks the API to use the LLM renderer (fails closed to the
    // template when no ANTHROPIC_API_KEY / on validation failure). The
    // production `vite build` the harness serves has DEV=false → always template.
    const panel = createAskPanel(askRoot, board, id, {
      useLlm: !!import.meta.env?.DEV, onSuperseded,
    });

    // harness + demo hook (read-only): drive the sixty-second script's first
    // frame from the URL (?ask=...) and expose probes for the screenshot tests.
    window.__cockpit = {
      ready: true,
      scheduleId: id,
      pinned,                     // the boot carried an explicit ?schedule= (CU1)
      picker,                     // the header schedule switcher (CU2)
      superseded: !!superseded,
      theme: currentTheme(),
      getTheme: currentTheme,
      setTheme: applyTheme,
      toggleTheme,
      board, panel, tray, coarseBand,
      ask: (q) => panel.run(q),
      select: (opRef) => board.select(opRef),
      highlight: (refs) => board.highlight(refs),
      clearHighlight: () => board.clearHighlight(),
      setWindow: (a, b) => board.setWindow(a, b),
      getWindow: () => board.getWindow(),
      overlayProbe: () => board.overlayProbe(),
      jumpToVersion,
      doc, meta,
    };

    // CU6: expose the real dev-ledger mount for the harness (which serves the
    // production build, so the auto-mount below is skipped) — a debug seam on the
    // existing harness object, never auto-invoked in production.
    window.__cockpit.mountDevLedger = () => mountDevLedger(chrome.right);

    // If this boot is the landing after an auto-follow (Session 4.4 CU2),
    // confirm the switch with a toast that offers a one-click way back. The
    // previous id was stashed in sessionStorage before the reload and read (+
    // cleared) at the top of boot, where it also decides `pinned`.
    if (followedFrom && followedFrom !== id) {
      followedToast(app, followedFrom);
      window.__cockpit.followedFrom = followedFrom;
    }

    if (superseded) {
      supersededBanner(app, meta.successor_id || null);
      window.__cockpit.successorId = meta.successor_id || null;
    } else {
      // Session 4.4 CU1/CU2: a stale tab must never leave the planner unknowingly
      // on anything but the newest relevant schedule. The watch re-checks the
      // whole data root on focus / tab re-show / a slow poll and either FOLLOWS
      // the newest live schedule (no uncommitted state — the resubmit-from-Excel
      // case) or offers the banner (uncommitted state present, user decides).
      // Runs only for a live (non-superseded) version; listing is background work.
      const hasUncommittedState = () => {
        const drag = window.__cockpit && window.__cockpit.drag;
        const phase = drag && drag.state ? drag.state().phase : "idle";
        const dragBusy = !!phase && phase !== "idle";
        const panelBusy = !!(panel && panel.hasUserState && panel.hasUserState());
        return dragBusy || panelBusy;
      };
      // Session 4B.23 Item 4: a LIVE SANDBOX PROPOSAL — a bar dropped and
      // awaiting its beats, or the delta card that followed it. The card
      // outlives the gesture (phase returns to idle while a refusal / failure /
      // no-verdict card stays up), so both are read.
      const proposalLive = () => {
        const drag = window.__cockpit && window.__cockpit.drag;
        if (!drag || !drag.state) return false;
        const st = drag.state();
        return (!!st.phase && st.phase !== "idle") || !!st.cardOpen;
      };
      const watch = installFreshnessWatch({
        app, boundId: id, hasUncommittedState, pinned,
        // CU4(b): the watch reads the board's window so it can put it back if
        // its own DOM insertion moved it. It never otherwise touches the board.
        board, proposalLive,
      });
      watch.check();   // notice a newer solve at boot too (the return-from-Excel tab)
      // Fetch the Tier-0 interaction payload in the BACKGROUND, after first
      // paint (R-T1d) — the board is already interactive read-only; the 3.2b
      // gesture surface stands up when it arrives. Never blocks render or ask.
      // The feel tuning panel (CU6) needs BOTH a dev build AND an explicit
      // opt-in (Session 4B.13 Item 5(b)). import.meta.env.DEV is true under
      // `vite` and false in the production `vite build` the harness serves, so
      // tuning never SHIPS — but Daryn's own dev server is a vite dev server,
      // which meant "FEEL TUNING · DEV" sat on screen during every walkthrough,
      // reading to a stranger as unfinished software. Off by default now; Daryn
      // keeps access with `?feel=1` (sticky per tab, `?feel=0` to clear).
      wireInteraction(id, board, window.__cockpit, {
        doc, devMode: !!import.meta.env?.DEV && feelTuningEnabled(), onSuperseded,
        // 4B.29 Item 1(d): the deeper search's SCALE, worded server-side.
        searchDeeperScale: (meta && meta.search_deeper) || null,
        // Session 4B.5 CU2: a priced delta card is the TOP of the ask panel's
        // resolution ladder. The controller publishes the card's own content
        // when one lands and null when it is dismissed / accepted / returned
        // home, so "what orders are affected in this move" is answered FROM the
        // card rather than guessed at by the nearest route.
        onCardChange: (card) => panel.setOpenCard(card),
        // Session 4B.3c CU4: "ask why" from a beat-two card bridges to the ask
        // panel with a real, grounded question. The rolling-explainer connector is
        // wired (the R-AI1 debt is retired), so this is a live answer, not a tip.
        // The question is composed from the moved op's INCUMBENT placement (the
        // board's truth): why the op is where it is — the context a planner weighing
        // the move actually wants. Returns true so the controller skips its tip.
        onAskWhy: (ctx) => {
          // Scoped to the sliced board (this session's subject); a monolithic card
          // keeps its panel-pointer tip. Both are honest — neither claims a debt.
          if (!doc.rolling) return false;
          const op = ctx && ctx.operation_ref;
          const a = op && (doc.assignments || []).find((x) => x.operation_ref === op);
          const wo = a && (a.work_orders || [])[0];
          const mach = a && a.external_name;
          if (!wo || !mach) return false;      // unresolvable → controller's tip
          if (board.select) board.select(op);  // scope the board to the op
          panel.run(`why is ${wo} on ${mach}?`);
          return true;
        },
        // An accepted/published edit rebinds the cockpit to the new version FULLY
        // (session 3.8 CU1): the address bar, the strip (new id + live status),
        // the ask panel target, the shared selection, and the harness hook all
        // follow the version the board now IS. No user action may be issued
        // against a superseded id from a live session.
        onVersionChange: async (newId, status) => {
          setUrlSchedule(newId);
          panel.setScheduleId(newId);
          panel.clearSelection();            // a moved op's old scope is stale
          window.__cockpit.scheduleId = newId;
          const nextMeta = await getScheduleMeta(newId).catch(() => meta);
          const nextDoc = board.currentDoc ? board.currentDoc() : doc;
          paintTopStrip(strip, { ...nextDoc, status }, nextMeta);
          window.__cockpit.versionChanged = { id: newId, status };
        },
      });
    }

    // The refusal-cluster dev panel (CU3, R-AI1(d)) — DEV-build-only, like the
    // feel tuning panel. Reads the DEV-gated /ledger/refusals; absent in the
    // production build the harness serves.
    if (import.meta.env?.DEV) mountDevLedger(chrome.right);

    if (CONFIG.autoAsk) panel.run(CONFIG.autoAsk);
  } catch (e) {
    app.querySelector(".split")?.remove();
    const err = document.createElement("div");
    err.className = "err";
    err.textContent = `cockpit could not load: ${e.message || e}`;
    app.appendChild(err);
    window.__cockpit = { ready: true, error: String(e.message || e) };
  }
}

boot();
