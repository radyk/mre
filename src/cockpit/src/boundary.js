// THE FROZEN-BOUNDARY CEREMONY (R-F1, Session 4B.28 Item 1).
//
// markers.js owns the HANDLE — hover, drag, the live instant and delta. This
// module owns everything that happens after the planner lets go, and the shape
// of it is R-F1(e): a boundary move restyles N bars, so the UI states the count
// and the direction and ASKS. An accidental three-day thaw of forty assignments
// must not happen from a slip of the wrist.
//
// THE COUNT IS NOT COMPUTED HERE. `POST /boundary/preview` returns the plan and
// its own sentence; the dialog prints them. The apply hands the preview's digest
// back, and the server refuses if the board changed in between. So there is
// exactly one place that decides what a boundary move does, and the number a
// planner confirms is the number that applies — the same discipline the delta
// card's `expect_delta_abs` uses since 4B.25.
//
// A REFUSAL IS AN ANSWER, NOT A FAILURE (4B.23). The server distinguishes
// "this board has no frozen boundary", "that is outside this window" and "the
// board changed under you" and sends each with its own sentence; the dialog
// shows the sentence and offers the one honest next act, which is to try again.
import { previewBoundary, postBoundary, getSchedule } from "./api.js";

const AUTHORITY = "dev-planner";

export function createBoundaryCeremony(hostEl, board, opts = {}) {
  const el = document.createElement("div");
  el.className = "boundary-confirm hidden";
  el.id = "boundary-confirm";
  hostEl.appendChild(el);

  let state = { phase: "idle", plan: null, last: null, error: null };

  function hide() {
    el.classList.add("hidden");
    el.replaceChildren();
    state = { ...state, phase: "idle", plan: null };
    if (opts.onOpenChange) opts.onOpenChange(false);
  }

  function shell(title, cls = "") {
    el.className = `boundary-confirm ${cls}`;
    el.replaceChildren();
    const head = document.createElement("div");
    head.className = "bc-head";
    head.textContent = title;
    el.appendChild(head);
    if (opts.onOpenChange) opts.onOpenChange(true);
    return el;
  }

  function body(text, cls = "bc-body") {
    const d = document.createElement("div");
    d.className = cls;
    d.textContent = text;              // server-composed prose — never innerHTML
    el.appendChild(d);
    return d;
  }

  function actions() {
    const row = document.createElement("div");
    row.className = "bc-actions";
    el.appendChild(row);
    return row;
  }

  function button(row, label, cls, onClick) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = cls;
    b.textContent = label;
    b.addEventListener("click", onClick);
    row.appendChild(b);
    return b;
  }

  // The refusal register: what the plant or the board says NO to. It carries no
  // "confirm" — there is nothing to confirm — and it never shows a raw error.
  function showRefusal(sentence, code) {
    state = { ...state, phase: "refused", plan: null, error: null };
    shell("The boundary did not move", "refused");
    body(sentence);
    el.dataset.code = code || "";
    const row = actions();
    button(row, "OK", "bc-dismiss", hide);
  }

  // The FAILURE register, which is a different thing and reads differently
  // (4B.23 §5a.91): the plant said nothing at all, because we could not ask it.
  function showFailure(what) {
    state = { ...state, phase: "failed", plan: null, error: what };
    shell("I could not move the boundary", "failed");
    body(`${what}. Nothing was changed — the boundary is where it was.`);
    const row = actions();
    button(row, "Try again", "bc-retry", () => {
      if (state.last) propose(state.last);
    });
    button(row, "Cancel", "bc-dismiss", hide);
  }

  // R-F1(e) — THE CONFIRMATION BEAT.
  function showPlan(plan) {
    state = { ...state, phase: "confirming", plan };
    shell(plan.direction === "thaw" ? "Thaw committed work?"
                                    : "Commit active work?",
          `confirm dir-${plan.direction}`);
    body(plan.sentence);
    const count = document.createElement("div");
    count.className = "bc-count";
    count.textContent = `${plan.count} placement${plan.count === 1 ? "" : "s"} `
      + (plan.direction === "thaw" ? "would become pins you hold"
                                   : "would become committed");
    el.appendChild(count);
    const row = actions();
    button(row, plan.direction === "thaw" ? "Thaw them" : "Commit them",
           "bc-apply", () => apply(plan));
    button(row, "Cancel", "bc-dismiss", hide);
  }

  function showApplying() {
    state = { ...state, phase: "applying" };
    shell("Moving the boundary…", "applying");
    body("Nothing is being re-solved — a boundary move changes who holds each "
       + "placement, never where it sits.");
  }

  function showDone(res) {
    state = { ...state, phase: "done" };
    const b = res.boundary || {};
    shell(b.direction === "thaw" ? "Thawed" : "Committed", "done");
    body(b.sentence || "The boundary moved.");
    const row = actions();
    button(row, "OK", "bc-dismiss", hide);
    setTimeout(() => { if (state.phase === "done") hide(); }, 4200);
  }

  // BEAT ONE of the ceremony: ask what the move would do.
  function propose(frozenUntilIso) {
    state = { ...state, last: frozenUntilIso };
    return previewBoundary(opts.scheduleId(), frozenUntilIso).then((plan) => {
      if (!plan || plan.refused) {
        showRefusal((plan && plan.sentence)
                    || "That is not a move this board can make.",
                    plan && plan.code);
        return null;
      }
      if (plan.direction === "none") {
        // 4B.28 Item 4(b)'s rule, on the boundary: a no-op SAYS SO. Nothing on
        // this board silently reverts any more.
        showRefusal(plan.sentence, "no_change");
        return null;
      }
      showPlan(plan);
      return plan;
    }).catch((e) => {
      showFailure(cause(e));
      return null;
    });
  }

  // BEAT TWO: apply exactly what was confirmed, then rebind the board.
  function apply(plan) {
    showApplying();
    return postBoundary(opts.scheduleId(), {
      frozen_until: plan.to_instant,
      authority: opts.authority || AUTHORITY,
      expect_digest: plan.digest,
    }).then((res) => {
      if (res && res.refused) {
        showRefusal(res.sentence, res.code);
        return null;
      }
      return getSchedule(res.schedule_id).then((newDoc) => {
        board.rebind(newDoc, { motion: opts.motion || {} });
        if (opts.onVersionChange) opts.onVersionChange(res.schedule_id, "proposed");
        showDone(res);
        return res;
      });
    }).catch((e) => {
      showFailure(cause(e));
      return null;
    });
  }

  function cause(e) {
    const status = e && e.status;
    if (status >= 500) return "the scheduler hit an error while working on it";
    if (status >= 400) return "the scheduler turned the request down";
    return "the connection to the scheduler dropped";
  }

  return {
    el,
    propose,
    hide,
    state: () => ({ ...state, open: !el.classList.contains("hidden") }),
  };
}
