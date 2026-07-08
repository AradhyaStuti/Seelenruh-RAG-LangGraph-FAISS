/**
 * useVoice — production-quality voice input hook
 *
 * Primary:  Web Speech API (SpeechRecognition) — instant start, built-in silence
 *           detection, no server round-trip, works in Chrome/Edge/Safari.
 * Fallback: MediaRecorder → Whisper server — for Firefox and any browser that
 *           doesn't support the Web Speech API.
 *
 * The lang prop maps directly to recognition language and Whisper lang code so
 * the full pipeline (STT → LLM → TTS) stays in the user's chosen language.
 */
import { useRef, useState, useCallback, useEffect } from "react";
import { getToken } from "@/lib/auth";

// BCP-47 locale codes for Web Speech API
const RECOGNITION_LANG = {
  en:   "en-US",
  hi:   "hi-IN",   // Works for Devanagari Hindi AND Hinglish
  de:   "de-DE",
  auto: "hi-IN",   // Indian-app default
};

// Lang codes forwarded to the Whisper transcription endpoint
const WHISPER_LANG = {
  en:   "en",
  hi:   "hi",
  de:   "de",
  auto: "hi",
};

function getSR() {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

export function isSpeechRecognitionSupported() {
  return !!getSR();
}

/**
 * @param {object} opts
 * @param {string}   opts.lang      — app lang code ("en" | "hi" | "de" | "auto")
 * @param {function} opts.onResult  — called with final transcript string
 * @param {function} opts.onError   — called with human-readable error string
 */
export function useVoice({ lang = "hi", onResult, onError }) {
  const [isListening, setIsListening]           = useState(false);
  const [interimTranscript, setInterimTranscript] = useState("");

  const recognitionRef      = useRef(null);
  const fallbackRecorderRef = useRef(null);
  const audioChunksRef      = useRef([]);
  const abortedRef          = useRef(false);
  const langRef             = useRef(lang);
  langRef.current = lang;

  // ── stop ──────────────────────────────────────────────────────────────────
  const stop = useCallback(() => {
    abortedRef.current = true;
    setIsListening(false);
    setInterimTranscript("");

    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (_) {}
      recognitionRef.current = null;
    }
    if (fallbackRecorderRef.current) {
      try {
        if (fallbackRecorderRef.current.state !== "inactive") {
          fallbackRecorderRef.current.stop();
        }
      } catch (_) {}
      fallbackRecorderRef.current = null;
    }
  }, []);

  // ── start ─────────────────────────────────────────────────────────────────
  const start = useCallback(async () => {
    // Toggle off if already listening
    if (isListening) { stop(); return; }
    abortedRef.current = false;
    setInterimTranscript("");

    const SR = getSR();

    // ── Primary: Web Speech API ────────────────────────────────────────────
    if (SR) {
      const recognition = new SR();
      recognitionRef.current = recognition;

      recognition.lang            = RECOGNITION_LANG[langRef.current] || "hi-IN";
      recognition.continuous      = false;   // auto-stops on silence
      recognition.interimResults  = true;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => setIsListening(true);

      recognition.onresult = (event) => {
        let interim = "";
        let finalText = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const t = event.results[i][0].transcript;
          if (event.results[i].isFinal) finalText += t;
          else interim += t;
        }
        setInterimTranscript(interim);
        if (finalText.trim()) {
          setInterimTranscript("");
          onResult?.(finalText.trim());
        }
      };

      recognition.onerror = (event) => {
        setIsListening(false);
        setInterimTranscript("");
        recognitionRef.current = null;

        if (event.error === "not-allowed" || event.error === "service-not-allowed") {
          onError?.("Microphone access denied. Please allow microphone access in your browser settings.");
          return;
        }
        if (event.error === "no-speech") return; // Normal — user didn't speak
        if (event.error === "aborted") return;   // Intentional stop
        // Other errors (network, audio-capture) — silently ignore to avoid noise
      };

      recognition.onend = () => {
        setIsListening(false);
        setInterimTranscript("");
        recognitionRef.current = null;
      };

      try {
        recognition.start();
      } catch (err) {
        setIsListening(false);
        onError?.("Could not start voice input. Please try again.");
      }
      return;
    }

    // ── Fallback: MediaRecorder → Whisper ──────────────────────────────────
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression:  true,
          autoGainControl:   true,
        },
      });

      const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"].find(
        (m) => MediaRecorder.isTypeSupported(m)
      ) || "";

      const recorder = mime
        ? new MediaRecorder(stream, { mimeType: mime })
        : new MediaRecorder(stream);

      fallbackRecorderRef.current = recorder;
      audioChunksRef.current      = [];

      recorder.ondataavailable = (e) => {
        if (e.data?.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setIsListening(false);

        if (abortedRef.current) return;

        const blob = new Blob(audioChunksRef.current, { type: mime || "audio/webm" });
        if (blob.size < 1000) return; // Too short — discard

        const reader = new FileReader();
        reader.onloadend = async () => {
          try {
            const token = getToken();
            const res   = await fetch("/api/transcribe", {
              method:  "POST",
              headers: {
                "Content-Type": "application/json",
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
              },
              body: JSON.stringify({
                audio: reader.result,
                lang:  WHISPER_LANG[langRef.current] || "hi",
              }),
            });
            const data = await res.json();
            if (data.text?.trim()) onResult?.(data.text.trim());
            else if (data.error)   onError?.(data.error);
          } catch {
            onError?.("Transcription failed. Please try again.");
          }
        };
        reader.readAsDataURL(blob);
      };

      recorder.start(250); // 250 ms timeslice — prevents empty blob on quick stop
      setIsListening(true);

      // Safety: auto-stop after 30 seconds
      setTimeout(() => {
        if (fallbackRecorderRef.current?.state === "recording") {
          fallbackRecorderRef.current.stop();
        }
      }, 30000);

    } catch (err) {
      setIsListening(false);
      if (err.name === "NotAllowedError") {
        onError?.("Microphone access denied. Please allow microphone access in your browser settings.");
      } else {
        onError?.("Could not access microphone. Please check your device.");
      }
    }
  }, [isListening, onResult, onError, stop]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortedRef.current = true;
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
    /** true when either the Web Speech API or getUserMedia is available */
    supported: typeof navigator !== "undefined" && (!!getSR() || !!navigator.mediaDevices),
  };
}
