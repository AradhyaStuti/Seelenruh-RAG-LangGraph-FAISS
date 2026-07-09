/**
 * useVoice — voice input hook
 *
 * Primary:  Web Speech API (single-utterance mode — browser handles silence)
 * Fallback: MediaRecorder → Whisper server (Firefox / unsupported browsers)
 *
 * Stale-closure safety: onResult and onError are stored in refs each render,
 * so recognition event handlers always call the latest callbacks.
 */
import { useRef, useState, useCallback, useEffect } from "react";
import { getToken } from "@/lib/auth";

const RECOGNITION_LANG = {
  en:   "en-US",
  hi:   "hi-IN",
  de:   "de-DE",
  // auto: use whatever language the browser is configured for
  auto: typeof navigator !== "undefined" ? (navigator.language || "en-US") : "en-US",
};

const WHISPER_LANG = {
  en:   "en",
  hi:   "hi",
  de:   "de",
  auto: "hi",
};

const HALLUCINATIONS = new Set([
  "thank you", "thank you for watching", "thanks for watching",
  "please subscribe", "like and subscribe", "see you next time",
  "hello", "welcome to the show", "bye", "goodbye",
  "you", "i", "um", "uh", "hmm", "the", "thanks",
  "okay", "ok", "hi", "hey", "silence", "music",
  "applause", "laughter", "no speech",
]);

function normalise(text) {
  return text.toLowerCase().replace(/[^\w\s]/g, "").replace(/\s+/g, " ").trim();
}

function isHallucination(text) {
  if (!text?.trim()) return true;
  const n = normalise(text);
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

export function useVoice({ lang = "hi", onResult, onError }) {
  const [isListening, setIsListening]             = useState(false);
  const [interimTranscript, setInterimTranscript] = useState("");

  const recognitionRef = useRef(null);
  const recorderRef    = useRef(null);
  const audioChunksRef = useRef([]);
  const abortedRef     = useRef(false);
  const abortCtrlRef   = useRef(null);
  const langRef        = useRef(lang);
  const recordStartRef = useRef(0);

  // Always-fresh callbacks — updated every render so async events never call stale functions
  const onResultRef = useRef(onResult);
  const onErrorRef  = useRef(onError);
  onResultRef.current = onResult;
  onErrorRef.current  = onError;
  langRef.current     = lang;

  const _setListening = useCallback((v) => {
    setIsListening(v);
    if (!v) setInterimTranscript("");
  }, []);

  // Fire the final transcript — filter hallucinations, then call onResult
  const _fire = useCallback((text) => {
    const clean = text?.trim();
    if (!clean || isHallucination(clean)) return;
    console.log("[voice] result:", JSON.stringify(clean));
    onResultRef.current?.(clean);
  }, []); // stable — uses ref

  // ── Stop ────────────────────────────────────────────────────────────────

  const stop = useCallback(() => {
    abortedRef.current = true;
    abortCtrlRef.current?.abort();
    abortCtrlRef.current = null;
    _setListening(false);
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (_) {}
      recognitionRef.current = null;
    }
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      try { recorderRef.current.stop(); } catch (_) {}
      recorderRef.current = null;
    }
  }, [_setListening]);

  // ── Whisper (MediaRecorder fallback) ────────────────────────────────────

  const _whisper = useCallback(async (blob, attempt = 0) => {
    if (abortedRef.current || blob.size < 3000) return;
    console.log(`[voice] whisper upload — ${(blob.size/1024).toFixed(1)} KB`);
    const ctrl = new AbortController();
    abortCtrlRef.current = ctrl;
    const reader = new FileReader();
    reader.onloadend = async () => {
      try {
        const token = getToken();
        const res = await fetch("/api/transcribe", {
          method: "POST",
          signal: ctrl.signal,
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ audio: reader.result, lang: WHISPER_LANG[langRef.current] || "hi" }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        console.log("[voice] whisper response:", data);
        if (data.text?.trim()) {
          _fire(data.text.trim());
        } else if (data.error && !abortedRef.current) {
          onErrorRef.current?.(data.error);
        }
      } catch (err) {
        if (err.name === "AbortError") return;
        console.error("[voice] whisper error:", err);
        if (attempt === 0 && !abortedRef.current) {
          await new Promise(r => setTimeout(r, 500));
          _whisper(blob, 1);
        } else if (!abortedRef.current) {
          onErrorRef.current?.("Transcription failed. Please try again.");
        }
      }
    };
    reader.readAsDataURL(blob);
  }, [_fire]);

  // ── Start ────────────────────────────────────────────────────────────────

  const start = useCallback(async () => {
    if (isListening) { stop(); return; }
    abortedRef.current = false;
    setInterimTranscript("");

    const SR = getSR();
    console.log(`[voice] start — SR: ${!!SR}, lang: ${langRef.current}`);

    // ── Web Speech API ─────────────────────────────────────────────────────
    if (SR) {
      const rec = new SR();
      recognitionRef.current = rec;
      rec.lang            = RECOGNITION_LANG[langRef.current] || "hi-IN";
      rec.continuous      = false;  // browser handles silence — simplest & most reliable
      rec.interimResults  = true;
      rec.maxAlternatives = 1;

      let transcript = ""; // accumulates across onresult events

      rec.onstart = () => {
        console.log("[voice] 🎤 started, lang:", rec.lang);
        _setListening(true);
      };

      rec.onresult = (event) => {
        // Rebuild full transcript from all results so far
        transcript = "";
        for (let i = 0; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }
        setInterimTranscript(transcript);
        console.log("[voice] interim:", JSON.stringify(transcript));
      };

      rec.onerror = (event) => {
        console.warn("[voice] error:", event.error);
        _setListening(false);
        recognitionRef.current = null;
        if (event.error === "not-allowed" || event.error === "service-not-allowed") {
          onErrorRef.current?.("Microphone access denied. Please allow microphone access in browser settings.");
        } else if (event.error === "language-not-supported") {
          // Retry with English if the selected language pack isn't available
          console.warn("[voice] language not supported — retrying with en-US");
          const rec2 = new SR();
          recognitionRef.current = rec2;
          rec2.lang = "en-US";
          rec2.continuous = false;
          rec2.interimResults = true;
          rec2.maxAlternatives = 1;
          let t2 = "";
          rec2.onstart  = () => _setListening(true);
          rec2.onresult = (e) => { t2 = ""; for (let i=0;i<e.results.length;i++) t2+=e.results[i][0].transcript; setInterimTranscript(t2); };
          rec2.onerror  = () => { _setListening(false); recognitionRef.current = null; };
          rec2.onend    = () => { _setListening(false); recognitionRef.current = null; const f=t2.trim(); t2=""; if(f) _fire(f); };
          try { rec2.start(); } catch(_) { _setListening(false); }
        } else if (event.error === "network") {
          onErrorRef.current?.("Network error during voice recognition. Please check your connection.");
        }
        // no-speech / aborted — silent
      };

      rec.onend = () => {
        console.log("[voice] ended, transcript:", JSON.stringify(transcript));
        _setListening(false);
        recognitionRef.current = null;
        const final = transcript.trim();
        transcript = "";
        if (final) _fire(final);
      };

      try {
        rec.start();
      } catch (err) {
        console.error("[voice] start error:", err);
        _setListening(false);
        onErrorRef.current?.("Could not start voice input. Please try again.");
      }
      return;
    }

    // ── MediaRecorder → Whisper fallback ───────────────────────────────────
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
        if (abortedRef.current) return;
        const ms = Date.now() - recordStartRef.current;
        if (ms < 1200) { console.log("[voice] too short — discarding"); return; }
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
        onErrorRef.current?.("Microphone access denied. Please allow microphone access in browser settings.");
      } else {
        onErrorRef.current?.("Could not access microphone. Please check your device settings.");
      }
    }
  }, [isListening, stop, _setListening, _fire, _whisper]);

  useEffect(() => () => {
    abortedRef.current = true;
    abortCtrlRef.current?.abort();
    if (recognitionRef.current) try { recognitionRef.current.abort(); } catch (_) {}
  }, []);

  return {
    isListening,
    interimTranscript,
    start,
    stop,
    supported: typeof navigator !== "undefined" && (!!getSR() || !!navigator.mediaDevices?.getUserMedia),
  };
}
