// Voice — tap-to-talk into the SAME ask path (docs/07 Phase 3 CU3; Session 3.7
// interaction model).
//
// The charter: ears for the answer, eyes for the footnotes. Speech-to-text (Web
// Speech API) feeds the transcript straight into the existing ask() route
// taxonomy — the deterministic explainer router IS the transcript→route mapper,
// and its honest "unsupported" bundle IS the low-confidence refusal (the LLM
// never authors answers; it only ever renders prose over evidence, fail-closed).
// Spoken responses give a SUMMARY sentence + the register aloud ("My take:" /
// "Testimony:") while the screen holds the receipts — record IDs are NEVER read
// aloud.
//
// Interaction model (Session 3.7): tap-to-start / tap-to-stop toggle — NOT a
// press-and-hold, which coupled the capture lifetime to the pointer sitting on a
// button that could shift out from under it. Recording is an explicit, latched
// state (push-to-talk EXPLICITNESS per docs/07 is preserved — the mic never
// opens itself). The interim transcript is streamed to a caller-owned overlay,
// never into the input; only the FINAL transcript lands, and only on stop.
// Escape cancels without submitting. An optional silence auto-stop is a
// convenience knob, OFF by default.
//
// Feature-detect and degrade to typed input WITHOUT drama: on a browser with no
// SpeechRecognition the mic simply doesn't mount; the typed composer is
// untouched.

// Silence auto-stop convenience (Session 3.7 CU2): after this much sustained
// quiet the recognizer stops itself (submitting what it heard). A token, tunable
// here; OFF by default at the call site — push-to-talk explicitness is the
// contract, this is only a courtesy for the "I stopped talking" case.
export const VOICE_SILENCE_MS = 2500;

// The recognition constructor: the vendor-prefixed Web Speech API on Chromium,
// OR a harness-injected fake (window.__VOICE_TEST_RECOGNITION) so the real UI
// path — mic mount, toggle, overlay, submit — is exercised without a microphone.
function recognitionCtor() {
  if (typeof window === "undefined") return null;
  return window.__VOICE_TEST_RECOGNITION
    || window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

export function speechRecognitionAvailable() {
  return !!recognitionCtor();
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

// A tap-to-talk controller: toggle() latches recording on/off. While recording,
// interim results stream to onInterim(text) (a caller-owned overlay — NEVER the
// input). onState("recording"|"idle") drives the recording affordance. On stop
// the accumulated FINAL transcript flows to onTranscript(text); cancel() (Escape)
// leaves recording WITHOUT submitting (onCancel fires instead). An optional
// silenceMs auto-stops after sustained quiet (0/falsy = off). Idempotent + safe
// where unsupported (returns a stub with available:false).
export function createVoiceInput({
  onTranscript, onInterim, onState, onCancel, silenceMs = 0,
} = {}) {
  const Ctor = recognitionCtor();
  if (!Ctor) {
    return {
      available: false,
      start() {}, stop() {}, cancel() {}, toggle() {}, listening: () => false,
    };
  }
  const rec = new Ctor();
  rec.lang = "en-US";
  rec.interimResults = true;
  // continuous: the session lives until the USER stops it (toggle) or silence
  // auto-stop fires — not until the engine's first pause. This is what keeps the
  // full sentence, never a leading fragment (Session 3.7 bug).
  rec.continuous = true;
  let listening = false;
  let cancelled = false;
  let finalText = "";      // accumulates across result events (never reset mid-session)
  let silenceTimer = null;

  function clearSilence() { if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; } }
  function armSilence() {
    if (!silenceMs) return;
    clearSilence();
    silenceTimer = setTimeout(() => stop(), silenceMs);
  }

  rec.onresult = (ev) => {
    let interim = "";
    for (let i = ev.resultIndex; i < ev.results.length; i++) {
      const r = ev.results[i];
      if (r.isFinal) finalText += r[0].transcript;
      else interim += r[0].transcript;
    }
    // paint the full running transcript (finals so far + the live interim) into
    // the overlay; the input is untouched until stop.
    if (onInterim) onInterim(`${finalText} ${interim}`.replace(/\s+/g, " ").trim());
    armSilence();   // any speech resets the quiet clock
  };
  rec.onerror = () => { listening = false; clearSilence(); onState && onState("idle"); };
  rec.onend = () => {
    listening = false;
    clearSilence();
    onState && onState("idle");
    const t = finalText.trim();
    finalText = "";
    if (cancelled) { cancelled = false; onCancel && onCancel(); return; }
    if (t && onTranscript) onTranscript(t);
  };

  function start() {
    if (listening) return;
    finalText = ""; cancelled = false;
    try { rec.start(); listening = true; onState && onState("recording"); }
    catch { listening = false; }
  }
  // stop → submit whatever was heard (via onend). cancel → discard it (Escape).
  function stop() { if (listening) { try { rec.stop(); } catch { /* */ } } }
  function cancel() {
    if (!listening) return;
    cancelled = true;
    try { (rec.abort || rec.stop).call(rec); } catch { /* */ }
  }

  return {
    available: true, start, stop, cancel,
    toggle() { listening ? stop() : start(); },
    listening: () => listening,
  };
}
