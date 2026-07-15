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
import { ask } from "./api.js";
import { createPushToTalk, speak, spokenSummary, speechRecognitionAvailable } from "./voice.js";

export function createAskPanel(rootEl, board, scheduleId, opts = {}) {
  // useLlm: send the `llm` flag to /ask. Enabled only in the dev build (main.js
  // passes import.meta.env.DEV). The server honors it solely when a key is set
  // and fails closed to the template renderer otherwise (CU6).
  const useLlm = !!opts.useLlm;
  // scheduleId is MUTABLE: an accepted edit rebinds the cockpit to a new version,
  // and a subsequent ask ("summarize my changes") must target it so the answer
  // reads the new version's evidence (where the planner_edit Decision lives).
  let selection = null;   // {operation_ref, work_orders, resource_id, resource_name}

  rootEl.innerHTML = `
    <h2>Ask the schedule <span class="sub">— M10 explainer, read-only</span></h2>
    <div class="log" id="ask-log">
      <div class="empty">Click a bar and ask “why is this here?”, or type a question
      (e.g. “why is ORD-000012 on F001-RES001?”).</div>
    </div>
    <div class="composer">
      <div class="scope" id="ask-scope"></div>
      <div class="row">
        <input id="ask-input" type="text" placeholder="ask a question…" autocomplete="off" />
        <button id="ask-mic" class="mic" title="hold to speak" aria-label="push to talk">🎤</button>
        <button id="ask-send">Ask</button>
      </div>
      <div class="voice-caption hidden" id="ask-caption"></div>
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
    scopeEl.innerHTML = `selected <b>${wo}</b> on <b>${selection.resource_name}</b>`;
    deicticBtn.disabled = false;
    deicticBtn.title = `ask: why is ${wo} on ${selection.resource_name}?`;
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

  function appendAnswer(text, meta) {
    clearEmpty();
    const register = meta?.register === "judgment" ? "judgment" : "testimony";
    const el = document.createElement("div");
    el.className = `msg answer ${register}`;
    const who = register === "judgment" ? "judgment" : "testimony";
    el.innerHTML = `<div class="who">${who}<span class="reg-chip">${register}</span></div><pre></pre><div class="cites"></div>`;
    el.querySelector("pre").textContent = text;
    // cited-bar highlight, in sync with the answer
    const refs = meta?.cited_refs;
    const lit = board.highlight(refs);
    const cites = el.querySelector(".cites");
    const nBars = lit?.bars?.length || 0;
    const laneNames = (lit?.lanes || []).map((r) => board.resourceName(r));
    if (nBars || laneNames.length) {
      cites.innerHTML = `lit <b>${nBars}</b> bar(s)` +
        (laneNames.length ? ` · lanes: <b>${laneNames.join(", ")}</b>` : "");
    } else {
      cites.remove();
    }
    logEl.appendChild(el); scrollDown();
    return el;
  }

  async function run(question, { spoken = false } = {}) {
    if (!question.trim()) return;
    appendYou(question);
    inputEl.value = "";
    try {
      const res = await ask(scheduleId, question, useLlm);
      appendAnswer(res.answer, res.bundle);
      // CU3: a voice-originated question gets a SPOKEN response — the register
      // aloud + a one-sentence summary; record IDs stay on screen, never voiced.
      if (spoken) speak(spokenSummary(res.answer, res.bundle?.register));
    } catch (e) {
      const el = document.createElement("div");
      el.className = "msg answer testimony";
      el.innerHTML = `<div class="who">error</div><pre></pre>`;
      el.querySelector("pre").textContent = String(e.message || e);
      logEl.appendChild(el); scrollDown();
    }
  }

  // Compile the RESOLVED question from the live selection BEFORE calling /ask —
  // external refs only (work_order + resource external_name), never the literal
  // "this" and never a canonical id. The router is left untouched; it only ever
  // sees a fully-resolved planner-vocabulary question (CU3).
  function deictic() {
    const wo = selection && (selection.work_orders || [])[0];
    if (!wo || !selection.resource_name) return;   // unresolvable — button is disabled anyway
    run(`why is ${wo} on ${selection.resource_name}?`);
  }

  function clearEmpty() { const e = logEl.querySelector(".empty"); if (e) e.remove(); }
  function scrollDown() { logEl.scrollTop = logEl.scrollHeight; }

  rootEl.querySelector("#ask-send").addEventListener("click", () => run(inputEl.value));
  inputEl.addEventListener("keydown", (e) => { if (e.key === "Enter") run(inputEl.value); });
  deicticBtn.addEventListener("click", deictic);
  rootEl.querySelector("#ask-clear").addEventListener("click", () => board.clearHighlight());

  // --- voice: push-to-talk into the same ask path (CU3) ----------------
  const micBtn = rootEl.querySelector("#ask-mic");
  const captionEl = rootEl.querySelector("#ask-caption");
  const ptt = createPushToTalk({
    onInterim: (t) => { captionEl.textContent = t; captionEl.classList.remove("hidden"); },
    onState: (s) => { micBtn.classList.toggle("listening", s === "listening"); },
    onTranscript: (t) => { captionEl.classList.add("hidden"); captionEl.textContent = ""; run(t, { spoken: true }); },
  });
  if (!ptt.available) {
    // degrade WITHOUT drama: no mic where SpeechRecognition is absent; the typed
    // composer is untouched.
    micBtn.remove();
  } else {
    // hold-to-talk (pointer), with a click fallback to toggle.
    micBtn.addEventListener("pointerdown", (e) => { e.preventDefault(); ptt.start(); });
    micBtn.addEventListener("pointerup", (e) => { e.preventDefault(); ptt.stop(); });
    micBtn.addEventListener("pointerleave", () => ptt.stop());
  }

  return {
    run, deictic,
    setScheduleId(id) { scheduleId = id; },
    // voice availability + a programmatic "speak this answer" seam for the
    // harness (which has no microphone): drive run() with {spoken:true}.
    voiceAvailable: () => speechRecognitionAvailable(),
    askSpoken(question) { return run(question, { spoken: true }); },
    // the pure spoken-summary builder, surfaced so the harness can assert the
    // "record IDs are never voiced" contract without a microphone (CU3).
    spokenSummary,
    selectAndAsk(operationRef) { board.select(operationRef); },
  };
}
