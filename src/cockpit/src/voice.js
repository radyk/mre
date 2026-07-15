// Voice — push-to-talk into the SAME ask path (docs/07 Phase 3 CU3).
//
// The charter: ears for the answer, eyes for the footnotes. Push-to-talk
// speech-to-text (Web Speech API) feeds the transcript straight into the
// existing ask() route taxonomy — the deterministic explainer router IS the
// transcript→route mapper, and its honest "unsupported" bundle IS the
// low-confidence refusal (the LLM never authors answers; it only ever renders
// prose over evidence, fail-closed). Spoken responses give a SUMMARY sentence +
// the register aloud ("My take:" / "Testimony:") while the screen holds the
// receipts — record IDs are NEVER read aloud.
//
// Feature-detect and degrade to typed input WITHOUT drama: on a browser with no
// SpeechRecognition the mic simply doesn't mount; the typed composer is
// untouched.

// The Web Speech API is vendor-prefixed on Chromium.
export function speechRecognitionAvailable() {
  return typeof window !== "undefined"
    && !!(window.SpeechRecognition || window.webkitSpeechRecognition);
}

export function speechSynthesisAvailable() {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

// Build the SPOKEN response from a rendered answer + its register. Pure and
// testable — the single place the "ears for the answer" contract is enforced:
//   * lead with the register aloud ("My take:" for judgment, "Testimony:" else);
//   * a ONE-sentence summary (the answer's first sentence/line);
//   * strip anything id-shaped (UUIDs, record ids, snap-… , dec-…) — record IDs
//     are never voiced; the screen holds them.
export function spokenSummary(answerText, register) {
  const lead = register === "judgment" ? "My take." : "Testimony.";
  const firstLine = (answerText || "")
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l && !l.startsWith("===") && !l.startsWith("register:"));
  let sentence = firstLine || "See the answer on screen.";
  // one sentence only
  const stop = sentence.search(/[.!?]\s/);
  if (stop > 0) sentence = sentence.slice(0, stop + 1);
  sentence = stripIds(sentence);
  return `${lead} ${sentence}`.replace(/\s+/g, " ").trim();
}

// Remove id-shaped tokens (never voiced): UUIDs, dec-/snap-/pool- prefixes, and
// bare long hex ids. Planner vocabulary (WO-2001, M-GEAR-01) is kept — those are
// the customer's own words, not record ids.
function stripIds(s) {
  return s
    .replace(/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi, "")
    .replace(/\b(?:dec|snap|pool|alt|run|sched)-[0-9a-z]{4,}\b/gi, "")
    .replace(/\b[0-9a-f]{12,}\b/gi, "")
    .replace(/\brerecord id[^.]*/i, "")
    .replace(/\(\s*\)/g, "")
    .trim();
}

// Speak a line aloud (best-effort; a no-op where synthesis is unavailable).
// Cancels any in-flight utterance so a new answer never talks over the old.
export function speak(text) {
  if (!speechSynthesisAvailable() || !text) return;
  try {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1.02;
    window.speechSynthesis.speak(u);
  } catch { /* speech is a courtesy, never load-bearing */ }
}

// A push-to-talk controller: hold the mic (pointerdown → start, pointerup →
// stop), transcript flows to onTranscript(text). Interim results paint a live
// caption via onInterim. Idempotent + safe to call where unsupported (the
// factory returns a stub with available:false).
export function createPushToTalk({ onTranscript, onInterim, onState } = {}) {
  if (!speechRecognitionAvailable()) {
    return { available: false, start() {}, stop() {}, toggle() {}, listening: () => false };
  }
  const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
  const rec = new Ctor();
  rec.lang = "en-US";
  rec.interimResults = true;
  rec.continuous = false;
  let listening = false;
  let finalText = "";

  rec.onresult = (ev) => {
    let interim = "";
    finalText = "";
    for (let i = ev.resultIndex; i < ev.results.length; i++) {
      const r = ev.results[i];
      if (r.isFinal) finalText += r[0].transcript;
      else interim += r[0].transcript;
    }
    if (interim && onInterim) onInterim(interim);
  };
  rec.onerror = () => { listening = false; onState && onState("idle"); };
  rec.onend = () => {
    listening = false;
    onState && onState("idle");
    const t = finalText.trim();
    if (t && onTranscript) onTranscript(t);
    finalText = "";
  };

  function start() {
    if (listening) return;
    finalText = "";
    try { rec.start(); listening = true; onState && onState("listening"); }
    catch { listening = false; }
  }
  function stop() { if (listening) { try { rec.stop(); } catch { /* */ } } }

  return {
    available: true, start, stop,
    toggle() { listening ? stop() : start(); },
    listening: () => listening,
  };
}
