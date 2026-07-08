import { getToken } from "@/lib/auth";

let currentAudio = null;
let currentUtterance = null;
let currentFetchAbortCtrl = null; // AbortController for in-flight /api/tts request

// Safari requires a user-gesture to unlock audio. We keep a flag and
// try to unlock on the first interaction.
let _safariUnlocked = false;

/**
 * Truncate text at the last sentence boundary before maxLen chars.
 * Avoids cutting mid-sentence which sounds bad in TTS.
 */
function _truncateAtSentence(text, maxLen) {
  if (text.length <= maxLen) return text;
  const sub = text.slice(0, maxLen);
  // Find last sentence-ending punctuation — include Devanagari danda (।)
  const lastEnd = Math.max(
    sub.lastIndexOf(". "),
    sub.lastIndexOf("! "),
    sub.lastIndexOf("? "),
    sub.lastIndexOf("।"),
    sub.lastIndexOf("\n"),
  );
  // Only use the boundary if it's past the halfway point (avoids tiny fragments)
  if (lastEnd > maxLen * 0.45) {
    return sub.slice(0, lastEnd + 1).trim();
  }
  return sub.trimEnd() + "…";
}

function isSafari() {
  return (
    /^((?!chrome|android).)*safari/i.test(navigator.userAgent) ||
    (navigator.vendor && navigator.vendor.indexOf("Apple") !== -1 &&
      navigator.userAgent.indexOf("CriOS") === -1 &&
      navigator.userAgent.indexOf("FxiOS") === -1)
  );
}

// Detect iOS version — older versions (< 16) have more restrictive audio policies
function iOSVersion() {
  const match = navigator.userAgent.match(/OS (\d+)_/);
  return match ? parseInt(match[1], 10) : null;
}

function isOldIOS() {
  const v = iOSVersion();
  return v !== null && v < 16;
}

function unlockSafariAudio() {
  if (_safariUnlocked || !isSafari()) return;
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const buf = ctx.createBuffer(1, 1, 22050);
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.connect(ctx.destination);
    src.start(0);
    ctx.resume().then(() => { _safariUnlocked = true; });
  } catch (_) {
    _safariUnlocked = true;
  }
}

export function isSpeechSupported() { return true; }

// Wrap audio.load() with a timeout — some Safari versions hang indefinitely.
function loadWithTimeout(audio, ms = 6000) {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms); // resolve (not reject) so we always proceed
    try {
      const p = audio.load();
      if (p && typeof p.then === "function") {
        p.then(() => { clearTimeout(timer); resolve(); })
         .catch(() => { clearTimeout(timer); resolve(); });
      } else {
        // load() returned nothing — wait for canplay or timeout
        audio.addEventListener("canplay", () => { clearTimeout(timer); resolve(); }, { once: true });
      }
    } catch (_) {
      clearTimeout(timer);
      resolve();
    }
  });
}

async function speakViaServer(text, opts) {
  // Cancel any previous in-flight TTS fetch before starting a new one
  currentFetchAbortCtrl?.abort();
  const ctrl = new AbortController();
  currentFetchAbortCtrl = ctrl;

  const token = getToken();
  const res = await fetch("/api/tts", {
    method: "POST",
    signal: ctrl.signal,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      // Truncate at sentence boundary — never mid-word / mid-sentence
      text: _truncateAtSentence(text, 800),
      domain: opts?.domain ?? "Mental Health",
      lang: opts?.lang ?? "en",
    }),
  });
  currentFetchAbortCtrl = null; // fetch completed — clear ref
  if (!res.ok) throw new Error(`TTS ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const audio = new Audio();

  audio.src = url;
  audio.preload = "auto";

  let endedFired = false;
  const fireEnd = () => {
    if (endedFired) return;
    endedFired = true;
    URL.revokeObjectURL(url);
    opts?.onEnd?.();
    if (currentAudio === audio) currentAudio = null;
  };

  audio.onplay = () => opts?.onStart?.();
  audio.onended = fireEnd;
  audio.onerror = fireEnd;

  // Safari: force-end after duration + 1.5s buffer if onended never fires
  audio.onloadedmetadata = () => {
    if (isSafari() && audio.duration && isFinite(audio.duration)) {
      setTimeout(fireEnd, (audio.duration + 1.5) * 1000);
    }
  };

  cancelSpeech();
  currentAudio = audio;

  // Use timeout-wrapped load() to avoid Safari hang
  await loadWithTimeout(audio);

  try {
    await audio.play();
  } catch (err) {
    if (err.name === "NotAllowedError") {
      // Autoplay policy blocked — signal UI, then throw so speak() falls back to browser TTS
      fireEnd();
      opts?.onPlayBlocked?.();
      throw err; // bubble up so speak() catch block triggers speakViaBrowser fallback
    }
    // Any other error — bubble up so speakViaBrowser fallback kicks in
    throw err;
  }
}

// Pick the best available Hindi voice.
// Priority: Google Hindi > Microsoft Hindi neural > any hi-IN voice.
function _bestHindiVoice() {
  if (!("speechSynthesis" in window)) return null;
  const voices = window.speechSynthesis.getVoices();
  if (!voices.length) return null;
  const hi = voices.filter((v) => v.lang.startsWith("hi") || v.lang === "hi-IN");
  if (!hi.length) return null;
  const tests = [
    (v) => /google.*hindi/i.test(v.name),
    (v) => /google/i.test(v.name) && v.lang.startsWith("hi"),
    (v) => /swara/i.test(v.name),          // Google Hindi (Android)
    (v) => /kalpana/i.test(v.name),        // Microsoft Hindi
    (v) => /hemant/i.test(v.name),         // Microsoft Hindi male
    (v) => /microsoft.*hindi/i.test(v.name),
    () => hi[0],
  ];
  for (const test of tests) {
    const match = hi.find(test) || (test.length === 0 ? hi[0] : null);
    if (match) return match;
  }
  return hi[0] || null;
}

// Pick the most natural-sounding English voice available in the browser.
// Priority: Google neural > Apple Samantha > Microsoft Aria/natural > any English.
function _bestEnglishVoice() {
  if (!("speechSynthesis" in window)) return null;
  const voices = window.speechSynthesis.getVoices();
  if (!voices.length) return null;
  const en = voices.filter((v) => v.lang.startsWith("en"));
  const tests = [
    (v) => /google us english/i.test(v.name),
    (v) => /google uk english female/i.test(v.name),
    (v) => /google/i.test(v.name) && /english/i.test(v.name),
    (v) => /samantha/i.test(v.name),
    (v) => /karen/i.test(v.name),
    (v) => /aria.*natural/i.test(v.name),
    (v) => /microsoft.*aria/i.test(v.name),
    (v) => /microsoft.*zira/i.test(v.name),
    (v) => /microsoft/i.test(v.name) && /english/i.test(v.lang),
    () => en[0],
  ];
  for (const test of tests) {
    const match = en.find(test) || (test.length === 0 ? en[0] : null);
    if (match) return match;
  }
  return null;
}

// Pick best German voice
function _bestGermanVoice() {
  if (!("speechSynthesis" in window)) return null;
  const voices = window.speechSynthesis.getVoices();
  if (!voices.length) return null;
  const de = voices.filter((v) => v.lang.startsWith("de"));
  if (!de.length) return null;
  const tests = [
    (v) => /google.*deutsch/i.test(v.name),
    (v) => /google/i.test(v.name) && v.lang.startsWith("de"),
    (v) => /microsoft.*hedda/i.test(v.name),   // Windows neural
    (v) => /microsoft.*katja/i.test(v.name),   // Windows Edge neural
    (v) => /microsoft.*german/i.test(v.name),
    () => de[0],
  ];
  for (const test of tests) {
    const match = de.find(test) || (test.length === 0 ? de[0] : null);
    if (match) return match;
  }
  return de[0] || null;
}

// Persona-specific browser TTS tuning
const _PERSONA_SPEECH = {
  "Mental Health":      { rate: 0.88, pitch: 1.02 },  // Usha: warm, slightly slower, natural pitch
  "Legal":              { rate: 0.92, pitch: 0.90 },  // Umang: composed, slightly lower
  "Government Schemes": { rate: 0.90, pitch: 1.00 },  // Aarogya: warm, clear, helpful
  "Safety":             { rate: 1.00, pitch: 0.90 },  // Raksha: direct, authoritative
};

function speakViaBrowser(text, opts) {
  if (!("speechSynthesis" in window) || !text.trim()) { opts?.onEnd?.(); return; }
  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(text);
  const lang = opts?.lang ?? "en";
  const domain = opts?.domain ?? "Mental Health";
  const isHindi = lang === "hi";
  const isGerman = lang === "de";

  let voice = null;
  if (isHindi) voice = _bestHindiVoice() || _bestEnglishVoice();
  else if (isGerman) voice = _bestGermanVoice() || _bestEnglishVoice();
  else voice = _bestEnglishVoice();

  if (voice) {
    utt.voice = voice;
    utt.lang = voice.lang;
  } else {
    utt.lang = isHindi ? "hi-IN" : isGerman ? "de-DE" : "en-US";
  }

  const speechCfg = _PERSONA_SPEECH[domain] || _PERSONA_SPEECH["Mental Health"];
  // Hindi: slightly slower for clarity
  utt.rate = isHindi ? speechCfg.rate * 0.95 : speechCfg.rate;
  utt.pitch = speechCfg.pitch;
  utt.volume = 1;

  let endedFired = false;
  const fireEnd = () => {
    if (endedFired) return;
    endedFired = true;
    opts?.onEnd?.();
    if (currentUtterance === utt) currentUtterance = null;
  };

  utt.onstart = () => opts?.onStart?.();
  utt.onend = fireEnd;
  utt.onerror = fireEnd;

  // Safety timeout — ~11 chars/sec (slower than English for Hindi/German).
  // fireEnd is idempotent so this is a no-op if onend fires correctly.
  const estMs = Math.max(5000, (text.length / 11) * 1000) + 4000;
  setTimeout(fireEnd, estMs);

  currentUtterance = utt;
  window.speechSynthesis.speak(utt);

  // Safari bug: speechSynthesis pauses after ~15s without this keepalive
  if (isSafari()) {
    const keepAlive = setInterval(() => {
      if (!window.speechSynthesis.speaking) { clearInterval(keepAlive); return; }
      window.speechSynthesis.pause();
      window.speechSynthesis.resume();
    }, 12000);
    utt.onend = () => { clearInterval(keepAlive); fireEnd(); };
    utt.onerror = () => { clearInterval(keepAlive); fireEnd(); };
  }
}

export function speak(text, opts) {
  if (!text?.trim()) return;
  unlockSafariAudio();
  // browserOnly=true: skip server TTS and speak immediately via browser.
  // Use this in real-time voice mode to cut ~3s of gTTS round-trip latency.
  if (opts?.browserOnly || isOldIOS()) {
    speakViaBrowser(text, opts);
    return;
  }
  speakViaServer(text, opts).catch((err) => {
    // NotAllowedError handled inside speakViaServer — don't fall through
    if (err?.name === "NotAllowedError") return;
    // AbortError: cancelSpeech() was called mid-fetch — don't start new audio
    if (err?.name === "AbortError") return;
    speakViaBrowser(text, opts);
  });
}

export function cancelSpeech() {
  // Abort any in-flight /api/tts fetch so the response is never played
  if (currentFetchAbortCtrl) {
    try { currentFetchAbortCtrl.abort(); } catch (_) {}
    currentFetchAbortCtrl = null;
  }
  if (currentAudio) {
    try { currentAudio.pause(); } catch (_) {}
    currentAudio = null;
  }
  if ("speechSynthesis" in window) {
    try { window.speechSynthesis.cancel(); } catch (_) {}
  }
  currentUtterance = null;
}

export function isSpeaking() {
  if (currentAudio && !currentAudio.paused && !currentAudio.ended) return true;
  return "speechSynthesis" in window && window.speechSynthesis.speaking;
}

export function primeVoices() {
  if ("speechSynthesis" in window) {
    // Chrome loads voices asynchronously — trigger load and listen for changes
    window.speechSynthesis.getVoices();
    window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
  }
  unlockSafariAudio();
}

/** Return available voices for a given lang code — useful for debugging. */
export function availableVoicesFor(lang) {
  if (!("speechSynthesis" in window)) return [];
  return window.speechSynthesis.getVoices().filter((v) => v.lang.startsWith(lang));
}
