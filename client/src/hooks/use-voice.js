/**
 * useVoice — voice input hook
 *
 * Primary:  Web Speech API (continuous mode — user taps stop when done)
 * Fallback: MediaRecorder → Whisper server
 *
 * Design:
 *  - continuous=true: user controls stop, no auto-cutoff surprises
 *  - transcript accumulates all recognised text during the session
 *  - onend always fires the full transcript
 *  - onResultRef / onErrorRef updated each render — no stale closures
 */
import { useRef, useState, useCallback, useEffect } from "react";
import { getToken } from "@/lib/auth";

// BCP-47 tags for Web Speech API
const LANG_MAP = {
  en:   "en-US",
  hi:   "hi-IN",
  de:   "de-DE",
  auto: "en-US",   // safest default — most universally supported
};

// Whisper codes sent to the server
const WHISPER_LANG = { en: "en", hi: "hi", de: "de", auto: "hi" };

// Phrases that STT commonly hallucinates on silence / noise
const HALLUCINATIONS = new Set([
  "thank you", "thank you for watching", "thanks for watching",
  "please subscribe", "like and subscribe", "see you next time",
  "welcome to the show", "bye", "goodbye",
  "um", "uh", "hmm", "the", "thanks",
  "okay", "ok", "silence", "music", "applause", "laughter", "no speech",
]);

function isHallucination(text) {
  if (!text?.trim()) return true;
  const n = text.toLowerCase().replace(/[^\w\s]/g, "").replace(/\s+/g, " ").trim();
  if (HALLUCINATIONS.has(n)) return true;
  if (/^[\d\s:.\-,/]+$/.test(text.trim())) return true;
  const hasDevanagari = /[\u0900-\u097F]/.test(text);
  const hasLatin      = /[a-zA-Z]/.test(text);
  if (!hasDevanagari && !hasLatin) return true;
  return false;
}

function getSR() {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

export function isSpeechRecognitionSupported() { return !!getSR(); }

export function useVoice({ lang = "en", onResult, onError }) {
  const [isListening, setIsListening]             = useState(false);
  const [interimTranscript, setInterimTranscript] = useState("");

  const recogRef        = useRef(null);
  const recorderRef     = useRef(null);
  const audioChunksRef  = useRef([]);
  const abortedRef      = useRef(false);  // true only on unmount — prevents post-unmount state updates
  const userStopRef     = useRef(false);  // true when user tapped stop deliberately (suppress "no speech" toast)
  const abortCtrlRef    = useRef(null);
  const langRef         = useRef(lang);
  const recordStartRef  = useRef(0);
  const transcriptRef   = useRef(""); // accumulates speech during session

  // Always-fresh callbacks — updated every render
  const onResultRef = useRef(onResult);
  const onErrorRef  = useRef(onError);
  onResultRef.current = onResult;
  onErrorRef.current  = onError;
  langRef.current     = lang;

  const _setListening = useCallback((v) => {
    setIsListening(v);
    if (!v) setInterimTranscript("");
  }, []);

  // Fire the final recognised text
  const _fire = useCallback((text) => {
    const clean = text?.trim();
    console.log("[voice] _fire:", JSON.stringify(clean));
    if (!clean || isHallucination(clean)) {
      console.log("[voice] _fire: filtered (empty or hallucination)");
      return;
    }
    console.log("[voice] ✅ calling onResult with:", JSON.stringify(clean));
    onResultRef.current?.(clean);
  }, []);

  // ── Stop ────────────────────────────────────────────────────────────────

  const stop = useCallback(() => {
    console.log("[voice] stop()");
    // Do NOT set abortedRef here — that would block the MediaRecorder Whisper upload.
    // abortedRef is only set on unmount to prevent post-unmount state updates.
    // userStopRef lets onend know this was a deliberate user action (suppresses "no speech" toast).
    userStopRef.current = true;
    abortCtrlRef.current?.abort();
    abortCtrlRef.current = null;
    _setListening(false);
    if (recogRef.current) {
      clearTimeout(recogRef.current._safetyTimer); // prevent orphaned timer
      try { recogRef.current.stop(); } catch (_) {}
      // don't null here — let onend handle cleanup and fire transcript
    }
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      try { recorderRef.current.stop(); } catch (_) {}
      recorderRef.current = null;
    }
  }, [_setListening]);

  // ── Whisper fallback ─────────────────────────────────────────────────────

  const _whisper = useCallback(async (blob, attempt = 0) => {
    if (blob.size < 3000) { console.log("[voice] blob too small"); return; }
    console.log(`[voice] whisper upload ${(blob.size/1024).toFixed(1)} KB`);
    const ctrl = new AbortController();
    abortCtrlRef.current = ctrl;
    const reader = new FileReader();
    reader.onloadend = async () => {
      try {
        const token = getToken();
        const res = await fetch("/api/transcribe", {
          method: "POST", signal: ctrl.signal,
          headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
          body: JSON.stringify({ audio: reader.result, lang: WHISPER_LANG[langRef.current] || "en" }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        console.log("[voice] whisper →", data);
        if (data.text?.trim()) _fire(data.text.trim());
        else if (data.error) onErrorRef.current?.(data.error);
        else onErrorRef.current?.("No speech detected. Please try again.");
      } catch (err) {
        if (err.name === "AbortError") return;
        console.error("[voice] whisper error:", err);
        if (attempt === 0) { await new Promise(r => setTimeout(r, 500)); _whisper(blob, 1); }
        else onErrorRef.current?.("Transcription failed. Please try again.");
      }
    };
    reader.readAsDataURL(blob);
  }, [_fire]);

  // ── Start ────────────────────────────────────────────────────────────────

  const start = useCallback(async () => {
    if (isListening) { stop(); return; }

    abortedRef.current   = false;
    transcriptRef.current = "";
    setInterimTranscript("");

    const SR = getSR();
    const recognitionLang = LANG_MAP[langRef.current] || "en-US";
    console.log(`[voice] start — SR:${!!SR} lang:${langRef.current} → ${recognitionLang}`);

    // ── Web Speech API (primary) ─────────────────────────────────────────
    if (SR) {
      const rec = new SR();
      recogRef.current = rec;

      rec.lang            = recognitionLang;
      rec.continuous      = false;  // single-utterance: browser auto-fires onend when speech ends
      rec.interimResults  = true;
      rec.maxAlternatives = 1;

      rec.onstart = () => {
        console.log("[voice] 🎤 recognition started, lang:", rec.lang);
        _setListening(true);
      };

      rec.onresult = (event) => {
        // Accumulate ALL results (final + interim) into transcript
        let full = "";
        for (let i = 0; i < event.results.length; i++) {
          full += event.results[i][0].transcript + " ";
        }
        full = full.trim();
        transcriptRef.current = full;
        setInterimTranscript(full);
        console.log("[voice] onresult:", JSON.stringify(full));
      };

      rec.onerror = (event) => {
        console.warn("[voice] onerror:", event.error);
        // "no-speech" just means nothing heard yet — keep listening with continuous=true
        if (event.error === "no-speech") return;
        if (event.error === "aborted") return;

        _setListening(false);
        recogRef.current = null;

        if (event.error === "not-allowed" || event.error === "service-not-allowed") {
          onErrorRef.current?.("Microphone access denied. Please allow microphone in browser settings.");
        } else if (event.error === "language-not-supported") {
          onErrorRef.current?.(`Language ${recognitionLang} not supported. Switch to English in the language selector.`);
        } else if (event.error === "network") {
          onErrorRef.current?.("Network error. Please check your connection and try again.");
        } else {
          onErrorRef.current?.(`Voice error: ${event.error}. Please try again.`);
        }
      };

      rec.onend = () => {
        console.log("[voice] onend, transcript:", JSON.stringify(transcriptRef.current));
        _setListening(false);
        recogRef.current = null;
        const final = transcriptRef.current.trim();
        transcriptRef.current = "";
        const wasUserStop = userStopRef.current;
        userStopRef.current = false;
        if (final) {
          _fire(final);
        } else if (!abortedRef.current && !wasUserStop) {
          // Auto-ended with no speech (browser timeout / network) — tell the user
          console.log("[voice] onend with empty transcript");
          onErrorRef.current?.("No speech detected. Please tap the mic and speak clearly.");
        }
        // wasUserStop && !final → user tapped stop without speaking; stay silent (no toast)
      };

      try {
        rec.start();
        // 45-second safety auto-stop
        const safety = setTimeout(() => {
          if (recogRef.current) {
            console.log("[voice] safety stop after 45s");
            try { recogRef.current.stop(); } catch (_) {}
          }
        }, 45000);
        // Store safety timer ID on the recognition object so stop() can clear it
        rec._safetyTimer = safety;
      } catch (err) {
        console.error("[voice] rec.start() threw:", err);
        _setListening(false);
        recogRef.current = null;
        onErrorRef.current?.("Could not start voice input. Please try again.");
      }
      return;
    }

    // ── MediaRecorder → Whisper (fallback) ──────────────────────────────
    console.log("[voice] using MediaRecorder fallback");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
      });
      const mime = ["audio/webm;codecs=opus","audio/webm","audio/ogg;codecs=opus","audio/mp4"]
        .find(m => MediaRecorder.isTypeSupported(m)) || "";
      const recorder = mime
        ? new MediaRecorder(stream, { mimeType: mime, audioBitsPerSecond: 16000 })
        : new MediaRecorder(stream);

      recorderRef.current    = recorder;
      audioChunksRef.current = [];
      recordStartRef.current = Date.now();

      recorder.ondataavailable = (e) => { if (e.data?.size > 0) audioChunksRef.current.push(e.data); };

      const safetyTimer = setTimeout(() => {
        if (recorderRef.current?.state === "recording") recorderRef.current.stop();
      }, 45000);

      recorder.onstop = () => {
        clearTimeout(safetyTimer);
        stream.getTracks().forEach(t => t.stop());
        _setListening(false);
        userStopRef.current = false;
        if (abortedRef.current) return; // only true on unmount — skip upload
        const ms = Date.now() - recordStartRef.current;
        if (ms < 1200) { onErrorRef.current?.("Recording too short. Please hold the mic and speak."); return; }
        const blob = new Blob(audioChunksRef.current, { type: mime || "audio/webm" });
        console.log(`[voice] blob: ${(blob.size/1024).toFixed(1)} KB`);
        _whisper(blob);
      };

      recorder.start(250);
      _setListening(true);
      console.log("[voice] 🎤 MediaRecorder started");
    } catch (err) {
      console.error("[voice] media error:", err);
      _setListening(false);
      if (err.name === "NotAllowedError") {
        onErrorRef.current?.("Microphone access denied. Please allow microphone in browser settings.");
      } else {
        onErrorRef.current?.("Could not access microphone. Please check your device settings.");
      }
    }
  }, [isListening, stop, _setListening, _fire, _whisper]);

  // Cleanup on unmount
  useEffect(() => () => {
    abortedRef.current = true;
    abortCtrlRef.current?.abort();
    if (recogRef.current) {
      clearTimeout(recogRef.current._safetyTimer);
      try { recogRef.current.abort(); } catch (_) {}
    }
  }, []);

  return {
    isListening,
    interimTranscript,
    start,
    stop,
    supported: typeof navigator !== "undefined" && (!!getSR() || !!navigator.mediaDevices?.getUserMedia),
  };
}
