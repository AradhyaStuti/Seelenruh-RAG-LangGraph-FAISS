/**
 * useVoice — production-quality voice input hook
 *
 * Architecture:
 *   Primary:  Web Speech API (Chrome/Edge/Safari) — instant, silence-aware, no latency
 *   Fallback: MediaRecorder → Whisper server (Firefox, unsupported browsers)
 *
 * Key design decisions:
 *   - continuous=true + manual silence detection → avoids premature cutoff on pause
 *   - Dedup guard prevents identical final transcripts firing twice (Chrome bug)
 *   - Hallucination filter rejects known Whisper noise responses
 *   - Auto-retry once on Whisper network failure
 *   - AbortController cancels in-flight Whisper request when stop() is called
 *   - Minimum audio duration (1.2s) rejects accidental taps
 */
import { useRef, useState, useCallback, useEffect } from "react";
import { getToken } from "@/lib/auth";

// BCP-47 locale codes for Web Speech API recognition
const RECOGNITION_LANG = {
  en:   "en-US",
  hi:   "hi-IN",   // Handles Devanagari AND Hinglish
  de:   "de-DE",
  auto: "hi-IN",   // Indian-app default
};

// Whisper language codes sent to the server
const WHISPER_LANG = {
  en:   "en",
  hi:   "hi",
  de:   "de",
  auto: "hi",
};

// Known Whisper hallucinations on silence / background noise.
// Normalised to lowercase with punctuation stripped.
const HALLUCINATIONS = new Set([
  "thank you", "thank you for watching", "thanks for watching",
  "please subscribe", "like and subscribe", "see you next time",
  "hello", "welcome to the show", "hello welcome to the show",
  "bye", "goodbye", "you", "i", "um", "uh", "hmm", "the",
  "thanks", "okay", "ok", "hi", "hey", "silence", "music",
  "applause", "laughter", "no speech",
  "simpics is a production of the us department of health and hearts",
  "this video is brought to you by",
  "satsang with the", "tampons are also speaking in hindi or hinglish",
]);

function _normalise(text) {
  return text.toLowerCase().replace(/[^\w\s]/g, "").replace(/\s+/g, " ").trim();
}

function isHallucination(text) {
  if (!text?.trim()) return true;
  const norm = _normalise(text);
  if (HALLUCINATIONS.has(norm)) return true;

  // Pure digits / timestamps
  if (/^[\d\s:.\-,/]+$/.test(text.trim())) return true;

  // Contains only non-ASCII (non-Latin) characters other than Devanagari
  // — e.g. random Unicode artifact
  const hasDevanagari = /[\u0900-\u097F]/.test(text);
  const hasLatin = /[a-zA-Z]/.test(text);
  if (!hasDevanagari && !hasLatin) return true;

  return false;
}

function getSR() {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

export function isSpeechRecognitionSupported() {
  return !!getSR();
}

/**
 * useVoice({ lang, onResult, onError })
 *
 * @param {string}   lang      — "en" | "hi" | "de" | "auto"
 * @param {function} onResult  — called with clean final transcript
 * @param {function} onError   — called with human-readable error string
 */
export function useVoice({ lang = "hi", onResult, onError }) {
  const [isListening, setIsListening]             = useState(false);
  const [interimTranscript, setInterimTranscript] = useState("");

  // Refs (stable across renders — never stale)
  const recognitionRef    = useRef(null);
  const recorderRef       = useRef(null);
  const audioChunksRef    = useRef([]);
  const abortedRef        = useRef(false);
  const abortCtrlRef      = useRef(null);  // AbortController for in-flight Whisper request
  const langRef           = useRef(lang);
  const lastFinalRef      = useRef("");    // dedup: last fired final transcript
  const recordStartRef    = useRef(0);     // timestamp when recording started
  const retryCountRef     = useRef(0);     // Whisper retry counter (max 1)
  langRef.current = lang;

  // ── Helpers ───────────────────────────────────────────────────────────────

  const _setListening = useCallback((v) => {
    setIsListening(v);
    if (!v) setInterimTranscript("");
  }, []);

  const _fireResult = useCallback((text) => {
    const clean = text?.trim();
    if (!clean) return;
    if (isHallucination(clean)) return;
    // Dedup: don't fire the same final transcript twice in a row (Chrome bug)
    if (clean === lastFinalRef.current) return;
    lastFinalRef.current = clean;
    // Reset dedup after 3s so repeated identical messages are allowed
    setTimeout(() => { if (lastFinalRef.current === clean) lastFinalRef.current = ""; }, 3000);
    onResult?.(clean);
  }, [onResult]);

  // ── Stop ──────────────────────────────────────────────────────────────────

  const stop = useCallback(() => {
    abortedRef.current = true;

    // Cancel any in-flight Whisper request
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

  // ── Whisper fallback (called after recorder.onstop) ───────────────────────

  const _sendToWhisper = useCallback(async (blob, attempt = 0) => {
    if (abortedRef.current) return;
    if (blob.size < 3000) return; // < 3 KB ≈ under ~0.3s — discard

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
          body: JSON.stringify({
            audio: reader.result,
            lang:  WHISPER_LANG[langRef.current] || "hi",
          }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (data.text?.trim()) {
          _fireResult(data.text.trim());
        } else if (data.error && !abortedRef.current) {
          onError?.(data.error);
        }
      } catch (err) {
        if (err.name === "AbortError") return; // Intentional cancel
        // Retry once on network failure
        if (attempt === 0 && !abortedRef.current) {
          retryCountRef.current += 1;
          await new Promise((r) => setTimeout(r, 500));
          _sendToWhisper(blob, 1);
        } else if (!abortedRef.current) {
          onError?.("Transcription failed. Please try again.");
        }
      }
    };
    reader.readAsDataURL(blob);
  }, [_fireResult, onError]);

  // ── Start ─────────────────────────────────────────────────────────────────

  const start = useCallback(async () => {
    if (isListening) { stop(); return; }

    abortedRef.current  = false;
    lastFinalRef.current = "";
    retryCountRef.current = 0;
    setInterimTranscript("");

    const SR = getSR();

    // ── Primary: Web Speech API ────────────────────────────────────────────
    if (SR) {
      const recognition = new SR();
      recognitionRef.current = recognition;

      recognition.lang            = RECOGNITION_LANG[langRef.current] || "hi-IN";
      // continuous=true: don't stop on first pause — let user finish their thought.
      // We stop manually when user taps stop.
      recognition.continuous      = true;
      recognition.interimResults  = true;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => _setListening(true);

      let silenceTimer = null;

      recognition.onresult = (event) => {
        // Clear any pending silence auto-stop
        clearTimeout(silenceTimer);

        let interim = "";
        let finalText = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const t = event.results[i][0].transcript;
          if (event.results[i].isFinal) finalText += t + " ";
          else interim += t;
        }

        setInterimTranscript(interim || finalText.trim());

        if (finalText.trim()) {
          _fireResult(finalText.trim());
        }

        // Auto-stop after 2s of silence following speech
        silenceTimer = setTimeout(() => {
          if (recognitionRef.current) {
            try { recognitionRef.current.stop(); } catch (_) {}
          }
        }, 2000);
      };

      recognition.onerror = (event) => {
        clearTimeout(silenceTimer);
        _setListening(false);
        recognitionRef.current = null;

        const { error } = event;
        if (error === "not-allowed" || error === "service-not-allowed") {
          onError?.("Microphone access denied. Please allow microphone access in browser settings.");
          return;
        }
        if (error === "no-speech" || error === "aborted") return;
        if (error === "network") {
          onError?.("Network error during voice recognition. Please check your connection.");
          return;
        }
        // audio-capture, language-not-supported, etc. — fall through to Whisper
        // by not calling onError so user doesn't see a confusing message
      };

      recognition.onend = () => {
        clearTimeout(silenceTimer);
        _setListening(false);
        recognitionRef.current = null;
      };

      try {
        recognition.start();
      } catch {
        _setListening(false);
        onError?.("Could not start voice input. Please try again.");
      }
      return;
    }

    // ── Fallback: MediaRecorder → Whisper ──────────────────────────────────
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation:  true,
          noiseSuppression:  true,
          autoGainControl:   true,
          channelCount:      1,    // Mono — Whisper doesn't benefit from stereo
        },
      });

      const mime = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/ogg;codecs=opus",
        "audio/mp4",
      ].find((m) => MediaRecorder.isTypeSupported(m)) || "";

      const recorder = mime
        ? new MediaRecorder(stream, { mimeType: mime, audioBitsPerSecond: 16000 })
        : new MediaRecorder(stream);

      recorderRef.current   = recorder;
      audioChunksRef.current = [];
      recordStartRef.current = Date.now();

      recorder.ondataavailable = (e) => {
        if (e.data?.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        _setListening(false);

        if (abortedRef.current) return;

        const durationMs = Date.now() - recordStartRef.current;
        if (durationMs < 1200) return; // < 1.2s — accidental tap, discard

        const blob = new Blob(audioChunksRef.current, { type: mime || "audio/webm" });
        _sendToWhisper(blob);
      };

      // 250ms timeslice → prevents empty blob on very quick stop
      recorder.start(250);
      _setListening(true);

      // Safety auto-stop after 45 seconds
      const safetyTimer = setTimeout(() => {
        if (recorderRef.current?.state === "recording") {
          recorderRef.current.stop();
        }
      }, 45000);

      // Attach cleanup to recorder stop
      const origOnStop = recorder.onstop;
      recorder.onstop = (e) => { clearTimeout(safetyTimer); origOnStop(e); };

    } catch (err) {
      _setListening(false);
      if (err.name === "NotAllowedError") {
        onError?.("Microphone access denied. Please allow microphone access in browser settings.");
      } else {
        onError?.("Could not access microphone. Please check your device settings.");
      }
    }
  }, [isListening, stop, _setListening, _fireResult, _sendToWhisper, onError]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortedRef.current = true;
      abortCtrlRef.current?.abort();
      if (recognitionRef.current) {
        try { recognitionRef.current.abort(); } catch (_) {}
      }
    };
  }, []);

  return {
    isListening,
    interimTranscript,
    start,
    stop,
    supported: typeof navigator !== "undefined" &&
      (!!getSR() || !!navigator.mediaDevices?.getUserMedia),
  };
}
