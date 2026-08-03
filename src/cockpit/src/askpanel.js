// The ask panel (CU4): embeds the M10 explainer against the rendered schedule.
// Three things make the evidence architecture spatial:
//   1. Registers render VISIBLY DISTINCT (testimony vs judgment) — they never
//      blend, mirroring the renderer's own discipline (honesty armor).
//   2. When an answer cites entities, the corresponding bars + lanes light up
//      on the board in sync — driven by the cited_refs the API surfaces, no new
//      answer path, no LLM access beyond the existing evidence.
//   3. Selection is shared: clicking a bar scopes a deictic "why is this here?"
//      to it (the board tells us the work_order + resource; we compose the
//      question the explainer already understands).
import { ask, askPreflight } from "./api.js";
import { createVoiceInput, speak, spokenSummary, speechRecognitionAvailable } from "./voice.js";

export function createAskPanel(rootEl, board, scheduleId, opts = {}) {
  // useLlm: send the `llm` flag to /ask. Enabled only in the dev build (main.js
  // passes import.meta.env.DEV). The server honors it solely when a key is set
  // and fails closed to the template renderer otherwise (CU6).
  const useLlm = !!opts.useLlm;
  // onSuperseded(staleId): the version this panel targets was replaced — jump to
  // the live successor (session 3.8 CU3). A stale /ask 409s "superseded"; we
  // surface planner language + a jump, never the raw error string.
  const onSuperseded = opts.onSuperseded || null;
  // scheduleId is MUTABLE: an accepted edit rebinds the cockpit to a new version,
  // and a subsequent ask ("summarize my changes") must target it so the answer
  // reads the new version's evidence (where the planner_edit Decision lives).
  let selection = null;   // {operation_ref, work_orders, resource_id, resource_name}

  // Conversational context (Session 4A.1 CU2): a short rolling history + a stable
  // session id let the server resolve an elliptical follow-up ("and what about
  // it?") against the prior subject, and let the ledger link a refusal to its
  // later rephrase (R-AI1(d)). The server is stateless — the client carries this.
  const sessionId = `sess-${Math.random().toString(36).slice(2, 10)}`;
  const askHistory = [];   // [{question, resolved_question, route, order, machine}]
  // Session 4A.3c CU1: the resolved subject of the PRIOR answer ({order|machine}),
  // sent back on the next /ask so a follow-up after a TYPED entity question ("why
  // is ORD-05 late" → "but why?") carries a subject even with nothing selected. A
  // history built from the selection channel alone cannot supply this. Kept in
  // lockstep with runner.py resolved_subject — the harness carries EXACTLY this.
  let lastAnswered = {};

  // Session 4B.5 CU2 — THE OPEN DELTA CARD, the top of the resolution ladder.
  // The drag controller pushes the priced sandbox result here when a card lands
  // and clears it when the card is dismissed, accepted or superseded. While it is
  // set, "this move" / "these orders" / "the delta" bind to it and are answered
  // FROM it — the founder's "what orders are affected in this move" used to reach
  // `swap-move`, which guesses about two orders' slack while the affected set sat
  // on screen. The panel does not read the board for this: it holds exactly what
  // the card is showing, so the two surfaces state one set of numbers.
  let openCard = null;
  function cardContext() {
    return openCard && openCard.open ? openCard : {};
  }

  // Subject types whose subject_external_name is unambiguously an ORDER ref vs a
  // MACHINE ref. Ambiguous types (a bare "schedule" label may be either) carry
  // nothing — we never guess order-vs-machine.
  const ORDER_SUBJECTS = new Set(["demand", "start_reason", "contested_fact", "order_attributes"]);
  const MACHINE_SUBJECTS = new Set(["machine_idle"]);
  function resolvedSubject(meta) {
    const name = ((meta && meta.subject_external_name) || "").trim();
    if (!name || name === "?" || name === "all") return {};
    const st = meta && meta.subject_type;
    if (ORDER_SUBJECTS.has(st)) return { order: name };
    if (MACHINE_SUBJECTS.has(st)) return { machine: name };
    return {};
  }
  // Session 4.4 CU2: a question in flight is uncommitted user state — freshness
  // must never yank the board out from under an ask that is mid-round-trip.
  let asking = false;

  function currentSelectionRefs() {
    const wo = selection && (selection.work_orders || [])[0];
    return {
      order: wo || null,
      machine: (selection && selection.resource_name) || null,
      // Item 5(d): the SELECTED operation, not just its order. Carried so an
      // order-level question resolves to the bar the planner is pointing at.
      op_seq: (selection && selection.op_seq != null) ? selection.op_seq : null,
    };
  }

  rootEl.innerHTML = `
    <h2>Ask the schedule <span class="sub">— M10 explainer, read-only</span></h2>
    <div class="log" id="ask-log">
      <div class="empty">Click a bar and ask “why is this here?”, or type a question
      (e.g. “why is ORD-000012 on F001-RES001?”).</div>
    </div>
    <div class="composer">
      <!-- Interim transcript FLOATS above the composer (Session 3.7 CU1): a
           fixed-footprint overlay so streaming speech never reflows the row the
           mic lives in — nothing under an active pointer may move (R-M1 spirit). -->
      <div class="voice-overlay hidden" id="ask-voice-overlay" aria-live="polite">
        <span class="vo-dot" aria-hidden="true"></span>
        <span class="vo-label">recording</span>
        <span class="vo-text" id="ask-voice-text"></span>
      </div>
      <div class="scope" id="ask-scope"></div>
      <div class="row">
        <input id="ask-input" type="text" placeholder="ask a question…" autocomplete="off" />
        <button id="ask-mic" class="mic" title="tap to speak" aria-label="voice input"
                aria-pressed="false">🎤</button>
        <button id="ask-send">Ask</button>
      </div>
      <div class="row">
        <button class="ghost" id="ask-deictic" disabled>Why is this here?</button>
        <button class="ghost" id="ask-clear">Clear highlight</button>
      </div>
    </div>`;

  const logEl = rootEl.querySelector("#ask-log");
  const inputEl = rootEl.querySelector("#ask-input");
  const scopeEl = rootEl.querySelector("#ask-scope");
  const deicticBtn = rootEl.querySelector("#ask-deictic");

  function renderScope() {
    // The deictic ask is only well-formed when the selected bar resolves to an
    // external order ref (planner vocabulary) AND a resource name — otherwise
    // there is no honest "why is X on Y?" to compose. No selection (or an
    // order-less bar) → the button stays disabled with a hint, never a dead
    // control that fires a bare "why is this here?" at the router (CU3).
    const wo = selection && (selection.work_orders || [])[0];
    if (!wo || !selection.resource_name) {
      scopeEl.innerHTML = `<span class="scope-hint">click a bar to ask why it's placed there</span>`;
      deicticBtn.disabled = true;
      deicticBtn.title = "select a bar on the board first";
      return;
    }
    const op = selection.op_seq != null ? ` op${selection.op_seq}` : "";
    scopeEl.innerHTML = `selected <b>${wo}${op}</b> on <b>${selection.resource_name}</b>`;
    deicticBtn.disabled = false;
    deicticBtn.title = `ask: why is ${wo} placed where it is on ${selection.resource_name}?`;
  }

  // shared selection: a clicked bar scopes the deictic ask (R-DP shared state).
  board.onSelect((sel) => { selection = sel; renderScope(); });
  renderScope();   // show the "click a bar" hint before any selection

  function appendYou(text) {
    clearEmpty();
    const el = document.createElement("div");
    el.className = "msg you";
    el.innerHTML = `<div class="who">you</div><pre></pre>`;
    el.querySelector("pre").textContent = text;
    logEl.appendChild(el); scrollDown();
  }

  // Session 4A.y Item 3 — THE DISCLOSURE IS NOT GATED ON THE REWRITE.
  //
  // This block used to render only when the server had REWRITTEN the question,
  // and the resolution note only ever reached the screen as a hardcoded
  // "[from board selection]" bracket — a substring test standing in for a
  // sentence. Since the listening docket the note carries the GRAIN and the
  // DIRECTION too, and both of those are defaulted on questions that need no
  // rewrite at all. Measured on the demo board, at HEAD:
  //
  //   "when does ORD-000126 op30 finish"
  //     note: "answered for the whole of ORD-000126 — you named op30 and this
  //            route answers at order level"
  //     rewritten: NO   ->  the planner saw none of it
  //
  // So the docket's own disclosure was invisible in the product it was built
  // for. Two changes: the block renders whenever a note EXISTS, and the note is
  // rendered VERBATIM instead of being reduced to a bracket. CU3 (Session 4A.3)
  // is not lost — "resolved against ORD-000128 (from board selection)" is the
  // note's own first clause, so it now says strictly more than the bracket did.
  //
  // The resolved question keeps its own <pre>, and keeps it EMPTY when nothing
  // was rewritten: a planner is never read their own sentence back
  // (`_with_assumptions`'s rule, honoured on this side of the wire too).
  function appendResolved(resolved, note, rewritten) {
    clearEmpty();
    const el = document.createElement("div");
    el.className = "msg resolved-note";
    el.innerHTML = `<div class="who">interpreted as</div><pre></pre>`
      + `<div class="assumed"></div>`;
    el.querySelector("pre").textContent = rewritten ? resolved : "";
    if (!rewritten) el.querySelector("pre").remove();
    const noteEl = el.querySelector(".assumed");
    if (note) noteEl.textContent = note; else noteEl.remove();
    logEl.appendChild(el); scrollDown();
  }

  function appendAnswer(text, meta) {
    clearEmpty();
    // Session 4A.5b (R-AI5(4)): `synthesis` joins the register vocabulary — an
    // answer the assistant reasoned to from the evidence because no contracted
    // route covered the question. Anything unrecognized still reads as testimony.
    const REGISTERS = { judgment: 1, synthesis: 1, testimony: 1 };
    const register = REGISTERS[meta?.register] ? meta.register : "testimony";
    const el = document.createElement("div");
    el.className = `msg answer ${register}`;
    const who = register;
    el.innerHTML = `<div class="who">${who}<span class="reg-chip">${register}</span></div><pre></pre><div class="cites"></div>`;
    el.querySelector("pre").textContent = text;
    // cited-bar highlight, in sync with the answer
    const refs = meta?.cited_refs;
    const lit = board.highlight(refs);
    const cites = el.querySelector(".cites");
    // Session 4B.14 Item 5(c) — CITE WHAT THE ANSWER USED. This line used to
    // fuse the lanes the answer narrated with the alternatives it merely had
    // available, so two bars on CUT-01 reported four lanes, two of them at 0%
    // utilisation — empty machines presented as evidence. The two channels are
    // separate on the wire now and they read as different claims here: lanes
    // are where the cited work RUNS, alternatives are roads the answer weighed.
    const nBars = lit?.bars?.length || 0;
    const laneNames = (lit?.lanes || []).map((r) => board.resourceName(r));
    const altNames = (lit?.alternatives || []).map((r) => board.resourceName(r));
    if (nBars || laneNames.length || altNames.length) {
      cites.innerHTML = `lit <b>${nBars}</b> bar(s)` +
        (laneNames.length ? ` · on: <b>${laneNames.join(", ")}</b>` : "") +
        (altNames.length ? ` · alternatives weighed: <b>${altNames.join(", ")}</b>` : "");
    } else {
      cites.remove();
    }
    logEl.appendChild(el); scrollDown();
    return el;
  }

  // BEAT ONE (Session 4A.5c CU3a): an honest non-answer while the second tier
  // reads. Never a fake answer and never an invented progress figure — it says
  // what is happening and commits to nothing about what will be found. Removed
  // the moment beat two lands, whether that is an answer or an error.
  function appendWaiting(text) {
    clearEmpty();
    const el = document.createElement("div");
    el.className = "msg answer synthesis waiting";
    el.setAttribute("aria-live", "polite");
    el.innerHTML = `<div class="who">synthesis<span class="reg-chip">reading</span></div><pre></pre>`;
    el.querySelector("pre").textContent = text;
    logEl.appendChild(el); scrollDown();
    return el;
  }

  async function run(question, { spoken = false } = {}) {
    if (!question.trim()) return;
    appendYou(question);
    inputEl.value = "";
    asking = true;
    let waitingEl = null;
    try {
      const ctx = {
        history: askHistory.slice(-4),
        card: cardContext(),
        selection: currentSelectionRefs(),
        lastAnswered,
        sessionId,
      };
      // Two-phase: ask which tier will answer BEFORE asking for the answer. The
      // preflight never throws (it resolves to the route tier on any failure), so
      // this adds a branch, not a failure mode. The server remembers the parse,
      // so the ask below does not pay for a second one.
      const pre = await askPreflight(scheduleId, question, ctx);
      if (pre && pre.tier === "synthesis" && pre.waiting) {
        waitingEl = appendWaiting(pre.waiting);
      }
      const res = await ask(scheduleId, question, useLlm, ctx);
      if (waitingEl) { waitingEl.remove(); waitingEl = null; }
      // CU2: an elliptical follow-up the server resolved shows the question it
      // actually answered (the deictic pattern from 3.2d, generalized).
      const resolved = res.bundle && res.bundle.resolved_question;
      const note = res.bundle && res.bundle.resolution_note;
      const rewritten = !!(resolved && resolved !== question);
      if (rewritten || note) appendResolved(resolved, note, rewritten);
      appendAnswer(res.answer, res.bundle);
      // remember this turn (subject refs from the live selection) for follow-ups
      const refs = currentSelectionRefs();
      askHistory.push({
        question, resolved_question: resolved || question,
        route: (res.bundle && res.bundle.route) || null,
        // Session 4A.y Item 5: the GRAIN travels with the turn. The repeat rider
        // compares what a question was ABOUT, and two clicks on two operations of
        // one order are two subjects, not one asked twice. The key is always
        // present (null when nothing is selected) — an ABSENT key means "this
        // client does not report the grain", which the server reads differently.
        order: refs.order, machine: refs.machine, op_seq: refs.op_seq ?? null,
      });
      // Carry this answer's resolved subject into the next question (CU1).
      lastAnswered = resolvedSubject(res.bundle);
      // CU3: a voice-originated question gets a SPOKEN response — the register
      // aloud + a one-sentence summary; record IDs stay on screen, never voiced.
      if (spoken) speak(spokenSummary(res.answer, res.bundle?.register));
    } catch (e) {
      if (waitingEl) { waitingEl.remove(); waitingEl = null; }
      // A superseded target is not an error to show raw (session 3.8 CU3): word
      // it as the plan having moved on, and offer a one-click jump to current.
      if (e && e.superseded) return appendSuperseded();
      appendTransportError(e, question);
    } finally {
      asking = false;
    }
  }

  // Session 4B.14 Item 5(a) — A TRANSPORT FAILURE IS NOT A CONVERSATIONAL TURN.
  //
  // Measured live: "ERROR / Failed to fetch" rendered in the log with the same
  // chrome as an answer. That string is the browser telling us the request never
  // reached the server; presenting it in the register a planner reads answers in
  // says the system considered their question and this is what it came back
  // with. It is not testimony, it has no register, and there is nothing to
  // audit — what it needs is to say plainly that nothing was asked yet, and to
  // offer the retry that is the only useful next action.
  function appendTransportError(e, question) {
    clearEmpty();
    const raw = String((e && e.message) || e || "");
    // A network-layer failure ("Failed to fetch", "NetworkError", a timeout)
    // versus a server that answered with a status. Different sentences: one
    // means the question never arrived, the other means it arrived and failed.
    const offline = /failed to fetch|networkerror|load failed|timeout|aborted/i.test(raw);
    const el = document.createElement("div");
    el.className = "msg transport-error";
    const said = offline
      ? "I couldn't reach the server, so your question hasn't been asked yet."
      : "The server couldn't answer that request.";
    el.innerHTML =
      `<div class="who">connection</div><pre></pre>` +
      `<div class="cites"><button class="retry-ask" type="button">Try again</button>` +
      `<span class="detail"></span></div>`;
    el.querySelector("pre").textContent = said;
    el.querySelector(".detail").textContent = raw;
    el.querySelector(".retry-ask").addEventListener("click", () => {
      el.remove();
      run(question);
    });
    logEl.appendChild(el); scrollDown();
  }

  // Planner-language notice + jump when the asked version was replaced (CU3).
  function appendSuperseded() {
    clearEmpty();
    const el = document.createElement("div");
    el.className = "msg answer superseded-note";
    el.innerHTML = `<div class="who">note</div>
      <pre>This plan was replaced by a newer version, so it no longer answers questions.</pre>
      <div class="row"><button class="jump-current">View current plan →</button></div>`;
    el.querySelector(".jump-current").addEventListener("click", () => {
      if (onSuperseded) onSuperseded(scheduleId);
    });
    logEl.appendChild(el); scrollDown();
  }

  // Compile the RESOLVED question from the live selection BEFORE calling /ask —
  // external refs only (work_order + resource external_name), never the literal
  // "this" and never a canonical id. The router is left untouched; it only ever
  // sees a fully-resolved planner-vocabulary question (CU3).
  function deictic() {
    const wo = selection && (selection.work_orders || [])[0];
    if (!wo || !selection.resource_name) return;   // unresolvable — button is disabled anyway
    // Session 4B.14 Item 2 — THE BUTTON NOW ASKS ITS OWN QUESTION. It is
    // labelled "Why is this here?" and fired "why is X on Y?", which is
    // `why-on-machine`: a CAPABILITY question, answered with which machines
    // could have run the step. That is a fine answer to a question the button
    // does not ask. "Here" is a position in TIME as much as on a lane, and the
    // blocker analysis is what answers it.
    run(`why is ${wo} placed where it is on ${selection.resource_name}?`);
  }

  function clearEmpty() { const e = logEl.querySelector(".empty"); if (e) e.remove(); }
  function scrollDown() { logEl.scrollTop = logEl.scrollHeight; }

  rootEl.querySelector("#ask-send").addEventListener("click", () => run(inputEl.value));
  inputEl.addEventListener("keydown", (e) => { if (e.key === "Enter") run(inputEl.value); });
  deicticBtn.addEventListener("click", deictic);
  rootEl.querySelector("#ask-clear").addEventListener("click", () => board.clearHighlight());

  // --- voice: tap-to-talk into the same ask path (CU3; Session 3.7 model) ---
  const micBtn = rootEl.querySelector("#ask-mic");
  const overlayEl = rootEl.querySelector("#ask-voice-overlay");
  const overlayTextEl = rootEl.querySelector("#ask-voice-text");
  let voiceState = "idle";

  const voice = createVoiceInput({
    // Silence auto-stop is a convenience, OFF by default (explicit tap-to-stop is
    // the contract). Flip to VOICE_SILENCE_MS to enable.
    silenceMs: 0,
    // interim → the FLOATING overlay only; the input is never touched mid-record.
    onInterim: (t) => { overlayTextEl.textContent = t; },
    onState: (s) => {
      voiceState = s === "recording" ? "recording" : "idle";
      const rec = voiceState === "recording";
      micBtn.classList.toggle("recording", rec);
      micBtn.setAttribute("aria-pressed", String(rec));
      micBtn.title = rec ? "tap to stop · Esc cancels" : "tap to speak";
      overlayEl.classList.toggle("hidden", !rec);
      if (!rec) overlayTextEl.textContent = "";
    },
    // The FINAL transcript lands in the input on stop (never the interim), then
    // runs on the spoken path (register aloud + one-sentence summary).
    onTranscript: (t) => { inputEl.value = t; run(t, { spoken: true }); },
    // Escape / cancel: leave recording, submit nothing, clear the overlay.
    onCancel: () => { overlayTextEl.textContent = ""; },
  });

  if (!voice.available) {
    // degrade WITHOUT drama: no mic where SpeechRecognition is absent; the typed
    // composer is untouched.
    micBtn.remove();
    overlayEl.remove();
  } else {
    // tap-to-start / tap-to-stop (Session 3.7): the capture no longer rides on a
    // held pointer, so a shifting button can't sever it mid-word.
    micBtn.addEventListener("click", (e) => { e.preventDefault(); voice.toggle(); });
    // Escape cancels an in-flight recording without submitting.
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && voice.listening()) { e.preventDefault(); voice.cancel(); }
    });
  }

  return {
    run, deictic,
    // Session 4B.28 Item 2(a): the collapsed ASK edge's badge — how many turns
    // this conversation holds. Null (no badge) on an untouched panel, because a
    // "0" beside a label a stranger has not used yet reads as an error count.
    turnCount() { return askHistory.length || null; },
    setScheduleId(id) { scheduleId = id; },
    // A version change may have MOVED the selected op (its resource/time is now
    // stale): drop the deictic scope so the next "why is this here?" is composed
    // from a fresh click on the rebound board (session 3.8 CU1).
    clearSelection() { selection = null; renderScope(); },
    // Session 4B.5 CU2 — the open delta card channel. `setOpenCard(payload)` when
    // a priced card lands; `setOpenCard(null)` when it is dismissed, accepted or
    // superseded. Clearing is not optional: a stale card would answer about a
    // move that is no longer on screen, which is worse than not answering.
    setOpenCard(card) { openCard = card && card.open ? card : null; },
    openCard: () => openCard,
    // Session 4.4 CU2: is the planner mid-investigation on THIS board? A live bar
    // selection (a pinned deictic scope), a conversation already built up, or an
    // ask in flight all count — auto-follow must yield the banner to any of them
    // ("an edit-in-flight outranks freshness", generalized to any user state).
    hasUserState() { return selection != null || askHistory.length > 0 || asking; },
    // voice availability + a programmatic "speak this answer" seam for the
    // harness (which has no microphone): drive run() with {spoken:true}.
    voiceAvailable: () => speechRecognitionAvailable(),
    askSpoken(question) { return run(question, { spoken: true }); },
    // the pure spoken-summary builder, surfaced so the harness can assert the
    // "record IDs are never voiced" contract without a microphone (CU3).
    spokenSummary,
    // the voice controller + its live state, surfaced for the harness (which
    // drives a fake recognizer): assert toggle latching, layout stability during
    // interim, and the full-transcript (no-fragment) submission (Session 3.7).
    voice,
    voiceState: () => voiceState,
    selectAndAsk(operationRef) { board.select(operationRef); },
  };
}
