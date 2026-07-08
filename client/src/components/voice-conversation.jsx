import { useEffect, useRef, useState, useCallback } from "react";

// ──────────────────────────────────────────────
// Persona configuration
// ──────────────────────────────────────────────
export const PERSONA_CFG = {
  "Mental Health": {
    name: "Usha",
    role: "Mental Wellness Guide",
    color: "#C96B8A",
    bg: "#FEF4F7",
    initials: "U",
  },
  Legal: {
    name: "Umang",
    role: "Legal Guidance Expert",
    color: "#7C5ABF",
    bg: "#FAF7FE",
    initials: "U",
  },
  "Government Schemes": {
    name: "Aarogya",
    role: "Schemes Navigator",
    color: "#4BA376",
    bg: "#F4FDF8",
    initials: "A",
  },
  Safety: {
    name: "Raksha",
    role: "Safety & Emergency Guide",
    color: "#D4606A",
    bg: "#FEF4F4",
    initials: "R",
  },
};

// ──────────────────────────────────────────────
// Hooks
// ──────────────────────────────────────────────

/** Blinks the eyes every 3–7 seconds while `active`. Returns `true` during blink. */
export function useBlinking(active) {
  const [blinking, setBlinking] = useState(false);
  const timerRef = useRef(null);

  const scheduleBlink = useCallback(() => {
    const delay = 3000 + Math.random() * 4000;
    timerRef.current = setTimeout(() => {
      if (!active) return;
      setBlinking(true);
      setTimeout(() => {
        setBlinking(false);
        scheduleBlink();
      }, 160);
    }, delay);
  }, [active]);

  useEffect(() => {
    if (!active) {
      clearTimeout(timerRef.current);
      setBlinking(false);
      return;
    }
    scheduleBlink();
    return () => clearTimeout(timerRef.current);
  }, [active, scheduleBlink]);

  return blinking;
}

/** Oscillates 0→1 at 110ms intervals when `speaking`. */
export function useMouthOpen(speaking) {
  const [open, setOpen] = useState(0);
  const timerRef = useRef(null);

  useEffect(() => {
    if (!speaking) {
      clearInterval(timerRef.current);
      setOpen(0);
      return;
    }
    timerRef.current = setInterval(() => {
      setOpen((v) => (v > 0.5 ? 0.15 : 0.8 + Math.random() * 0.2));
    }, 110);
    return () => clearInterval(timerRef.current);
  }, [speaking]);

  return open;
}

/** 12 bar heights that animate when recording. */
export function useMicBars(isRecording) {
  const [bars, setBars] = useState(Array(12).fill(0.2));
  const timerRef = useRef(null);

  useEffect(() => {
    if (!isRecording) {
      clearInterval(timerRef.current);
      setBars(Array(12).fill(0.2));
      return;
    }
    timerRef.current = setInterval(() => {
      setBars(Array.from({ length: 12 }, () => 0.2 + Math.random() * 0.8));
    }, 90);
    return () => clearInterval(timerRef.current);
  }, [isRecording]);

  return bars;
}

/** Types `text` character-by-character. Returns `{ displayed, done }`. */
export function useTypewriter(text, speed = 16) {
  const [displayed, setDisplayed] = useState("");
  const [done, setDone] = useState(false);
  const timerRef = useRef(null);
  const indexRef = useRef(0);

  useEffect(() => {
    if (!text) {
      setDisplayed("");
      setDone(false);
      indexRef.current = 0;
      return;
    }
    setDisplayed("");
    setDone(false);
    indexRef.current = 0;
    clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      indexRef.current += 1;
      setDisplayed(text.slice(0, indexRef.current));
      if (indexRef.current >= text.length) {
        clearInterval(timerRef.current);
        setDone(true);
      }
    }, speed);
    return () => clearInterval(timerRef.current);
  }, [text, speed]);

  return { displayed, done };
}

/** Rotates through `phrases` every `interval` ms while `active`. */
export function useRotatingPhrase(phrases, active, interval = 4000) {
  const [idx, setIdx] = useState(0);
  const timerRef = useRef(null);

  useEffect(() => {
    if (!active || phrases.length <= 1) {
      clearInterval(timerRef.current);
      return;
    }
    timerRef.current = setInterval(() => {
      setIdx((i) => (i + 1) % phrases.length);
    }, interval);
    return () => clearInterval(timerRef.current);
  }, [active, phrases, interval]);

  return phrases[idx] ?? "";
}

// ──────────────────────────────────────────────
// Mini persona orb (bottom switcher)
// ──────────────────────────────────────────────
function PersonaOrb({ domain, cfg, active, onClick }) {
  return (
    <button
      type="button"
      onClick={() => onClick(domain)}
      aria-label={`Switch to ${cfg.name}`}
      className="flex flex-col items-center gap-1 group"
    >
      <div
        className="h-11 w-11 rounded-full flex items-center justify-center text-white font-semibold text-sm transition-transform group-hover:scale-105"
        style={{
          backgroundColor: cfg.color,
          boxShadow: active
            ? `0 0 0 3px white, 0 0 0 5px ${cfg.color}`
            : "0 1px 4px rgba(0,0,0,0.15)",
        }}
      >
        {cfg.initials}
      </div>
      <span
        className="text-[10px] font-medium"
        style={{ color: active ? cfg.color : "#64748b" }}
      >
        {cfg.name}
      </span>
    </button>
  );
}

// ──────────────────────────────────────────────
// Professional SVG Avatar
// ──────────────────────────────────────────────
function PersonaAvatar({ cfg, blinking, mouthOpen, isSpeaking }) {
  const eyeScaleY = blinking ? 0.08 : 1;
  const mouthHeight = 4 + mouthOpen * 10;

  return (
    <svg
      width="120"
      height="120"
      viewBox="0 0 120 120"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <defs>
        <radialGradient id={`bg-${cfg.initials}`} cx="40%" cy="35%" r="65%">
          <stop offset="0%" stopColor={cfg.color} stopOpacity="0.9" />
          <stop offset="100%" stopColor={cfg.color} stopOpacity="1" />
        </radialGradient>
      </defs>

      {/* Glow ring when speaking */}
      {isSpeaking && (
        <circle
          cx="60"
          cy="60"
          r="58"
          fill="none"
          stroke={cfg.color}
          strokeWidth="2"
          opacity="0.35"
        />
      )}

      {/* Main circle */}
      <circle cx="60" cy="60" r="52" fill={`url(#bg-${cfg.initials})`} />

      {/* Initials */}
      <text
        x="60"
        y="54"
        textAnchor="middle"
        dominantBaseline="middle"
        fill="white"
        fontSize="26"
        fontFamily="'EB Garamond', Georgia, serif"
        fontWeight="600"
      >
        {cfg.initials}
      </text>

      {/* Eyes */}
      <ellipse
        cx="46"
        cy="74"
        rx="5"
        ry={5 * eyeScaleY}
        fill="white"
        opacity="0.85"
        style={{ transition: "ry 0.08s ease" }}
      />
      <ellipse
        cx="74"
        cy="74"
        rx="5"
        ry={5 * eyeScaleY}
        fill="white"
        opacity="0.85"
        style={{ transition: "ry 0.08s ease" }}
      />

      {/* Mouth */}
      {mouthOpen > 0.05 ? (
        <ellipse
          cx="60"
          cy="90"
          rx="8"
          ry={mouthHeight / 2}
          fill="white"
          opacity="0.7"
          style={{ transition: "ry 0.11s ease" }}
        />
      ) : (
        <path
          d="M52 90 Q60 94 68 90"
          fill="none"
          stroke="white"
          strokeWidth="2"
          strokeLinecap="round"
          opacity="0.7"
        />
      )}
    </svg>
  );
}

// ──────────────────────────────────────────────
// Ripple rings
// ──────────────────────────────────────────────
function RippleRings({ color, active }) {
  if (!active) return null;
  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none" aria-hidden>
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="absolute rounded-full border"
          style={{
            width: 120 + i * 36,
            height: 120 + i * 36,
            borderColor: color,
            opacity: 0.25 - i * 0.06,
            animation: `ripple 2s ease-out ${i * 0.5}s infinite`,
          }}
        />
      ))}
    </div>
  );
}

// ──────────────────────────────────────────────
// Waveform bars
// ──────────────────────────────────────────────
function WaveformBars({ bars, color }) {
  return (
    <div className="flex items-center gap-0.5 h-10" aria-hidden>
      {bars.map((h, i) => (
        <div
          key={i}
          className="w-1 rounded-full transition-all duration-75"
          style={{ height: `${h * 100}%`, backgroundColor: color, minHeight: 3 }}
        />
      ))}
    </div>
  );
}

// ──────────────────────────────────────────────
// Main VoiceConversationScreen
// ──────────────────────────────────────────────
export function VoiceConversationScreen({
  open,
  domain,
  onClose,
  onDomainChange,
  isRecording,
  isSpeakingAI,
  isThinking,
  lastUserMessage,
  lastAiMessage,
  onMicClick,
  onResend,
}) {
  const cfg = PERSONA_CFG[domain] ?? PERSONA_CFG["Mental Health"];
  const blinking = useBlinking(open);
  const mouthOpen = useMouthOpen(isSpeakingAI);
  const micBars = useMicBars(isRecording);
  // Skip typewriter animation while AI is speaking — show text instantly to match TTS
  const { displayed: displayedTranscript } = useTypewriter(lastAiMessage ?? "", isSpeakingAI ? 0 : 16);
  const [editedMsg, setEditedMsg] = useState("");
  const [isEditing, setIsEditing] = useState(false);

  // sync editable field when a new transcription arrives or modal reopens
  useEffect(() => {
    if (lastUserMessage) {
      setEditedMsg(lastUserMessage);
      setIsEditing(false);
    }
  }, [lastUserMessage, open]);


  const statusPhrases = isRecording
    ? ["Listening..."]
    : isThinking
    ? ["Thinking...", "Processing your message..."]
    : isSpeakingAI
    ? [`${cfg.name} is speaking...`]
    : ["Tap the microphone to speak"];

  const status = useRotatingPhrase(statusPhrases, open, 4000);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col"
      style={{ backgroundColor: cfg.bg }}
      role="dialog"
      aria-modal="true"
      aria-label={`Voice conversation with ${cfg.name}`}
    >
      {/* Top bar */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-black/5">
        <div className="flex items-center gap-3">
          <div
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: cfg.color }}
            aria-hidden
          />
          <div>
            <p className="font-headline text-base font-semibold" style={{ color: cfg.color }}>
              {cfg.name}
            </p>
            <p className="text-xs text-slate-500">{cfg.role}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close voice conversation"
          className="h-9 w-9 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 hover:bg-black/5 transition-colors text-lg font-light"
        >
          &#x2715;
        </button>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col items-center justify-start px-6 gap-6 overflow-y-auto pt-6">
        {/* Avatar + ripple rings */}
        <div className="relative flex items-center justify-center" style={{ width: 180, height: 180 }}>
          <RippleRings color={cfg.color} active={isSpeakingAI} />
          <PersonaAvatar
            cfg={cfg}
            blinking={blinking}
            mouthOpen={mouthOpen}
            isSpeaking={isSpeakingAI}
          />
        </div>

        {/* Status */}
        <p
          className="text-sm font-medium text-center animate-fade-in"
          style={{ color: cfg.color }}
          key={status}
        >
          {status}
        </p>

        {/* Waveform when recording */}
        {isRecording && (
          <div className="animate-fade-in">
            <WaveformBars bars={micBars} color={cfg.color} />
          </div>
        )}

        {/* User message — editable */}
        {lastUserMessage && (
          <div className="w-full max-w-sm">
            <div className="flex items-center justify-between mb-1.5">
              <p className="text-[11px] uppercase tracking-widest text-slate-400">You said</p>
              {!isThinking && !isSpeakingAI && !isRecording && (
                <button
                  type="button"
                  onClick={() => setIsEditing((v) => !v)}
                  className="text-[10px] font-medium px-2 py-0.5 rounded-full transition"
                  style={{ color: cfg.color, background: `${cfg.color}15` }}
                >
                  {isEditing ? "Cancel" : "Edit"}
                </button>
              )}
            </div>
            {isEditing ? (
              <div className="space-y-2">
                <textarea
                  rows={3}
                  value={editedMsg}
                  onChange={(e) => setEditedMsg(e.target.value)}
                  className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm resize-none focus:outline-none"
                  style={{ borderColor: `${cfg.color}40` }}
                />
                <button
                  type="button"
                  onClick={() => { setIsEditing(false); onResend?.(editedMsg.trim()); }}
                  disabled={!editedMsg.trim()}
                  className="w-full rounded-full py-2 text-sm font-semibold text-white transition disabled:opacity-40"
                  style={{ backgroundColor: cfg.color }}
                >
                  Send
                </button>
              </div>
            ) : (
              <div className="bg-white rounded-lg border border-black/8 px-4 py-3 text-sm text-slate-600 text-right shadow-sm">
                {editedMsg}
              </div>
            )}
          </div>
        )}

        {/* AI reply with typewriter */}
        {displayedTranscript && (
          <div className="w-full max-w-sm animate-slide-up">
            <p className="text-[11px] uppercase tracking-widest text-slate-400 mb-1.5">
              {cfg.name}
            </p>
            <div
              className="rounded-lg border px-4 py-3 text-sm leading-relaxed shadow-sm max-h-52 overflow-y-auto"
              style={{ borderColor: `${cfg.color}30`, backgroundColor: `${cfg.color}08` }}
            >
              <p style={{ color: "#0F172A" }}>{displayedTranscript}</p>
            </div>
          </div>
        )}
      </div>

      {/* Bottom — mic only */}
      <div className="px-6 pb-8 pt-4 border-t border-black/5 flex flex-col items-center gap-4">
        {/* Recording pulse ring */}
        <div className="relative flex items-center justify-center">
          {isRecording && (
            <>
              <div className="absolute rounded-full border-2 border-red-500 opacity-60"
                style={{ width: 88, height: 88, animation: "ripple 1.2s ease-out infinite" }} />
              <div className="absolute rounded-full border-2 border-red-400 opacity-30"
                style={{ width: 108, height: 108, animation: "ripple 1.2s ease-out 0.4s infinite" }} />
            </>
          )}
          <button
            type="button"
            onClick={onMicClick}
            aria-label={isRecording ? "Stop recording" : "Start recording"}
            disabled={isThinking}
            className="relative h-16 w-16 rounded-full flex items-center justify-center text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              backgroundColor: isRecording ? "#B91C1C" : cfg.color,
              boxShadow: isRecording
                ? "0 0 0 6px rgba(185,28,28,0.25), 0 4px 20px rgba(185,28,28,0.4)"
                : `0 4px 16px ${cfg.color}40`,
              transform: isRecording ? "scale(1.08)" : "scale(1)",
            }}
          >
            {isRecording ? (
              <svg width="20" height="20" viewBox="0 0 20 20" fill="white" aria-hidden>
                <rect x="4" y="4" width="12" height="12" rx="2" />
              </svg>
            ) : (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="23" />
                <line x1="8" y1="23" x2="16" y2="23" />
              </svg>
            )}
          </button>
        </div>
        <p className="text-sm font-medium" style={{ color: isRecording ? "#B91C1C" : "#64748b" }}>
          {isThinking ? "Thinking..." : isRecording ? "🔴 Listening — tap to send" : isSpeakingAI ? "Tap mic to interrupt" : "Tap to speak"}
        </p>
      </div>
    </div>
  );
}
