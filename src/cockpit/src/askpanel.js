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

export function createAskPanel(rootEl, board, scheduleId) {
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
    if (!selection) { scopeEl.innerHTML = ""; deicticBtn.disabled = true; return; }
    const wo = selection.work_orders[0] || "(op)";
    scopeEl.innerHTML = `selected <b>${wo}</b> on <b>${selection.resource_name}</b>`;
    deicticBtn.disabled = false;
  }

  // shared selection: a clicked bar scopes the deictic ask (R-DP shared state).
  board.onSelect((sel) => { selection = sel; renderScope(); });

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

  async function run(question) {
    if (!question.trim()) return;
    appendYou(question);
    inputEl.value = "";
    try {
      const res = await ask(scheduleId, question);
      appendAnswer(res.answer, res.bundle);
    } catch (e) {
      const el = document.createElement("div");
      el.className = "msg answer testimony";
      el.innerHTML = `<div class="who">error</div><pre></pre>`;
      el.querySelector("pre").textContent = String(e.message || e);
      logEl.appendChild(el); scrollDown();
    }
  }

  function deictic() {
    if (!selection) return;
    const wo = selection.work_orders[0];
    if (!wo) return;
    run(`why is ${wo} on ${selection.resource_name}?`);
  }

  function clearEmpty() { const e = logEl.querySelector(".empty"); if (e) e.remove(); }
  function scrollDown() { logEl.scrollTop = logEl.scrollHeight; }

  rootEl.querySelector("#ask-send").addEventListener("click", () => run(inputEl.value));
  inputEl.addEventListener("keydown", (e) => { if (e.key === "Enter") run(inputEl.value); });
  deicticBtn.addEventListener("click", deictic);
  rootEl.querySelector("#ask-clear").addEventListener("click", () => board.clearHighlight());

  return { run, deictic, selectAndAsk(operationRef) { board.select(operationRef); } };
}
