/**
 * useVoice — voice input hook
 *
 * Architecture:
 *   Primary:  Web Speech API (Chrome/Edge/Safari) — instant, no latency
 *   Fallback: MediaRecorder → Whisper server (Firefox, unsupported browsers)
 *
 * Key design decisions:
 *   - onResultRef / onErrorRef: updated every render so event handlers never
 *     call a stale callback regardless of when they fire.
 *   - _fireResult has [] deps (stable) — no stale-closure risk from onResult.
 *   - continuous=true + 2s silence gate → avoids premature cutoff.
 *   - Dedup guard prevents identical transcripts firing twice (Chrome quirk).
 *   - Hallucination filter rejects known Whisper noise phrases.
 */
import { useRef, useState, useCallback, useEffect } from "react";
import { getToken } from "@/lib/auth";

// BCP-47 locale codes for Web Speech API
const RECOGNITION_LANG = {
  en:   "en-US",
  hi:   "hi-IN",
  de:   "de-DE",
  auto: "hi-IN",
};

// Whisper language codes sent to the server
const WHISPER_LANG = {
  en:   "en",
  hi:   "hi",
  de:   "de",
  auto: "hi",
};

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

  // Core refs
  const recognitionRef  = useRef(null);
  const recorderRef     = useRef(null);
  const audioChunksRef  = useRef([]);
  const abortedRef      = useRef(false);
  const abortCtrlRef    = useRef(null);
  const langRef         = useRef(lang);
  const lastFinalRef    = useRef("");
  const recordStartRef  = useRef(0);
  const retryCountRef   = useRef(0);

  // ── Always-fresh callback refs ────────────────────────────────────────────
  // Updated on every render so recognition event handlers (which close over
  // these refs) always call the latest onResult/onError from the parent —
  // even if the parent re-renders with new state while recognition is running.
  const onResultRef = useRef(onResult);
  const onErrorRef  = useRef(onError);
  onResultRef.current = onResult;
  onErrorRef.current  = onError;
  langRef.current     = lang;

  // ── Helpers ───────────────────────────────────────────────────────────────

  const _setListening = useCallback((v) => {
    setIsListening(v);
    if (!v) setInterimTranscript("");
  }, []);

  // Stable ([] deps) — uses refs so it never goes stale no matter when called.
  const _fireResult = useCallback((text) => {
    const clean = text?.trim();
    if (!clean) {
      console.log("[voice] _fireResult: empty — skipping");
      return;
    }
    if (isHallucination(clean)) {
      console.log("[voice] _fireResult: hallucination filtered:", JSON.stringify(clean));
      return;
    }
    if (clean === lastFinalRef.current) {
      console.log("[voice] _fireResult: dedup — same as last result, skipping");
      return;
    }
    lastFinalRef.current = clean;
    setTimeout(() => { if (lastFinalRef.current === clean) lastFinalRef.current = ""; }, 3000);
    console.log("[voice] ✅ firing result:", JSON.stringify(clean));
    onResultRef.current?.(clean);
  }, []); // intentionally empty — uses onResultRef

  // ── Stop ──────────────────────────────────────────────────────────────────

  const stop = useCallback(() => {
    console.log("[voice] stop() called");
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

  // ── Whisper fallback ──────────────────────────────────────────────────────

  const _sendToWhisper = useCallback(async (blob, attempt = 0) => {
    if (abortedRef.current) return;
    if (blob.size < 3000) {
      console.log("[voice] blob too small (<3 KB) — discarding");
      return;
    }
    console.log(`[voice] sending to Whisper — ${(blob.size / 1024).toFixed(1)} KB, attempt ${attempt + 1}`);

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
        console.log("[voice] Whisper response:", data);
        if (data.text?.trim()) {
          _fireResult(data.text.trim());
        } else if (data.error && !abortedRef.current) {
          console.warn("[voice] STT error from server:", data.error);
          onErrorRef.current?.(data.error);
        } else {
          console.log("[voice] Whisper returned empty text — nothing to send");
        }
      } catch (err) {
        if (err.name === "AbortError") {
          console.log("[voice] Whisper request aborted");
          return;
        }
        console.error("[voice] Whisper fetch error:", err);
        if (attempt === 0 && !abortedRef.current) {
          retryCountRef.current += 1;
          console.log("[voice] retrying Whisper in 500ms");
          await new Promise((r) => setTimeout(r, 500));
          _sendToWhisper(blob, 1);
        } else if (!abortedRef.current) {
          onErrorRef.current?.("Transcription failed. Please try again.");
        }
      }
    };
    reader.readAsDataURL(blob);
  }, [_fireResult]); // _fireResult is stable so this is effectively []

  // ── Start ─────────────────────────────────────────────────────────────────

  const start = useCallback(async () => {
    if (isListening) {
      console.log("[voice] already listening — stopping");
      stop();
      return;
    }

    abortedRef.current    = false;
    lastFinalRef.current  = "";
    retryCountRef.current = 0;
    setInterimTranscript("");

    const SR = getSR();
    console.log(`[voice] start() — SR available: ${!!SR}, lang: ${langRef.current}`);

    // ── Primary: Web Speech API ────────────────────────────────────────────
    if (SR) {
      const recognition = new SR();
      recognitionRef.current = recognition;

      recognition.lang            = RECOGNITION_LANG[langRef.current] || "hi-IN";
      recognition.continuous      = true;
      recognition.interimResults  = true;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        console.log(`[voice] 🎤 recognition started, lang: ${recognition.lang}`);
        _setListening(true);
      };

      let silenceTimer     = null;
      let accumulatedFinal = "";
      let lastInterim      = "";

      recognition.onresult = (event) => {
        clearTimeout(silenceTimer);
        let interim   = "";
        let finalText = "";

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const t = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalText        += t + " ";
            accumulatedFinal += t + " ";
          } else {
            interim += t;
          }
        }

        lastInterim = interim;
        setInterimTranscript(interim || finalText.trim() || accumulatedFinal.trim());
        console.log(`[voice] onresult — interim: ${JSON.stringify(interim)} final: ${JSON.stringify(finalText.trim())}`);

        if (finalText.trim()) {
          _fireResult(finalText.trim());
        }

        // Auto-stop after 2s of silence
        silenceTimer = setTimeout(() => {
          console.log("[voice] silence timeout — stopping recognition");
          if (recognitionRef.current) {
            try { recognitionRef.current.stop(); } catch (_) {}
          }
        }, 2000);
      };

      recognition.onerror = (event) => {
        clearTimeout(silenceTimer);
        const { error } = event;
        console.warn("[voice] recognition error:", error);
        _setListening(false);
        recognitionRef.current = null;

        if (error === "not-allowed" || error === "service-not-allowed") {
          onErrorRef.current?.("Microphone access denied. Please allow microphone access in browser settings.");
          return;
        }
        if (error === "no-speech" || error === "aborted") return; // silent — expected
        if (error === "network") {
          onErrorRef.current?.("Network error during voice recognition. Please check your connection.");
          return;
        }
        // audio-capture, language-not-supported — fall through silently
      };

      recognition.onend = () => {
        clearTimeout(silenceTimer);
        console.log(`[voice] recognition ended — accumulated: ${JSON.stringify(accumulatedFinal.trim())} interim: ${JSON.stringify(lastInterim)}`);
        _setListening(false);
        recognitionRef.current = null;

        // Chrome with continuous=true often never marks results isFinal.
        // Flush whatever accumulated (prefer confirmed final, then interim).
        const best = (accumulatedFinal || lastInterim).trim();
        if (best && !accumulatedFinal.trim()) {
          console.log("[voice] flushing interim as result:", JSON.stringify(best));
          _fireResult(best);
        }
        accumulatedFinal = "";
        lastInterim      = "";
      };

      try {
        recognition.start();
        console.log("[voice] recognition.start() called");
      } catch (err) {
        console.error("[voice] recognition.start() threw:", err);
        _setListening(false);
        onErrorRef.current?.("Could not start voice input. Please try again.");
      }
      return;
    }

    // ── Fallback: MediaRecorder → Whisper ──────────────────────────────────
    console.log("[voice] using MediaRecorder fallback (no Web Speech API)");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl:  true,
          channelCount:     1,
        },
      });
      console.log("[voice] 🎤 microphone stream acquired");

      const mime = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/ogg;codecs=opus",
        "audio/mp4",
      ].find((m) => MediaRecorder.isTypeSupported(m)) || "";
      console.log("[voice] MIME type:", mime || "(browser default)");

      const recorder = mime
        ? new MediaRecorder(stream, { mimeType: mime, audioBitsPerSecond: 16000 })
        : new MediaRecorder(stream);

      recorderRef.current    = recorder;
      audioChunksRef.current = [];
      recordStartRef.current = Date.now();

      recorder.ondataavailable = (e) => {
        if (e.data?.size > 0) audioChunksRef.current.push(e.data);
      };

      const safetyTimer = setTimeout(() => {
        if (recorderRef.current?.state === "recording") {
          console.log("[voice] safety stop after 45s");
          recorderRef.current.stop();
        }
      }, 45000);

      recorder.onstop = () => {
        clearTimeout(safetyTimer);
        stream.getTracks().forEach((t) => t.stop());
        _setListening(false);
        console.log("[voice] 🎤 recording stopped");

        if (abortedRef.current) {
          console.log("[voice] aborted — discarding recording");
          return;
        }

        const durationMs = Date.now() - recordStartRef.current;
        console.log(`[voice] recording duration: ${durationMs}ms`);
        if (durationMs < 1200) {
          console.log("[voice] too short (<1.2s) — discarding");
          return;
        }

        const blob = new Blob(audioChunksRef.current, { type: mime || "audio/webm" });
        console.log(`[voice] 📦 audio blob: ${(blob.size / 1024).toFixed(1)} KB`);
        _sendToWhisper(blob);
      };

      recorder.start(250);
      _setListening(true);
      console.log("[voice] MediaRecorder started");

    } catch (err) {
      console.error("[voice] media access error:", err);
      _setListening(false);
      if (err.name === "NotAllowedError") {
        onErrorRef.current?.("Microphone access denied. Please allow microphone access in browser settings.");
      } else {
        onErrorRef.current?.("Could not access microphone. Please check your device settings.");
      }
    }
  }, [isListening, stop, _setListening, _fireResult, _sendToWhisper]);

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
