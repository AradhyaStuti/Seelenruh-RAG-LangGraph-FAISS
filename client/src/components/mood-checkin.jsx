import { useEffect, useState } from "react";
import { MoodFace } from "@/components/icons";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const MOODS = [
  {
    key: "joyful",
    label: "Joyful",
    color: "#16A34A",
    bg: "rgba(22,163,74,0.10)",
    border: "rgba(22,163,74,0.25)",
    affirmation: "Your joy is contagious. Carry this light with you today.",
    tip: "Share a kind word with someone — joy multiplies when spread.",
  },
  {
    key: "calm",
    label: "Calm",
    color: "#0891B2",
    bg: "rgba(8,145,178,0.10)",
    border: "rgba(8,145,178,0.25)",
    affirmation: "Stillness is strength. You are grounded and present.",
    tip: "A great time to reflect, journal, or do deep focused work.",
  },
  {
    key: "tired",
    label: "Tired",
    color: "#64748B",
    bg: "rgba(100,116,139,0.10)",
    border: "rgba(100,116,139,0.25)",
    affirmation: "Rest is not giving up — it is giving back to yourself.",
    tip: "Even 10 minutes of rest or a short walk can restore energy.",
  },
  {
    key: "anxious",
    label: "Anxious",
    color: "#D97706",
    bg: "rgba(217,119,6,0.10)",
    border: "rgba(217,119,6,0.25)",
    affirmation: "Anxiety is a signal, not a sentence. You are safe right now.",
    tip: "Try box breathing — inhale 4s, hold 4s, exhale 4s, hold 4s.",
  },
  {
    key: "sad",
    label: "Sad",
    color: "#7C3AED",
    bg: "rgba(124,58,237,0.10)",
    border: "rgba(124,58,237,0.25)",
    affirmation: "It is okay to feel sad. Every feeling deserves a gentle space.",
    tip: "Talk to Usha — she is here to listen without judgement.",
  },
];

const STORAGE_KEY = "seelenruh:mood:v1";
const today = () => new Date().toISOString().slice(0, 10);
const DAY_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function getMoodColor(moodKey) {
  return MOODS.find((m) => m.key === moodKey)?.color ?? null;
}

function getStreak(history) {
  let streak = 0;
  const d = new Date();
  for (let i = 0; i < 60; i++) {
    const iso = d.toISOString().slice(0, 10);
    if (history.find((r) => r.date === iso)) { streak++; d.setDate(d.getDate() - 1); }
    else break;
  }
  return streak;
}

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

export function MoodCheckIn({ onMoodChange }) {
  const [selected, setSelected] = useState(null);
  const [history, setHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        let data = JSON.parse(raw);
        // Prune entries older than 60 days to prevent unbounded growth
        const cutoff = new Date();
        cutoff.setDate(cutoff.getDate() - 60);
        const cutoffStr = cutoff.toISOString().slice(0, 10);
        data = data.filter((r) => r.date >= cutoffStr);
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
        setHistory(data);
        const todays = data.find((r) => r.date === today());
        if (todays) { setSelected(todays.mood); onMoodChange?.(todays.mood); }
      }
    } catch { /* ignore */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pick = (mood) => {
    const isToggleOff = selected === mood;
    const nextMood = isToggleOff ? null : mood;
    setSelected(nextMood);
    onMoodChange?.(nextMood);
    const next = isToggleOff
      ? history.filter((r) => r.date !== today())
      : [{ date: today(), mood }, ...history.filter((r) => r.date !== today())].slice(0, 60);
    setHistory(next);
    try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); } catch { /* ignore */ }
  };

  const selectedMood = MOODS.find((m) => m.key === selected);
  const streak = getStreak(history);

  // Last 14 days — fixed: rec = { date, mood } or undefined
  const last14 = Array.from({ length: 14 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - (13 - i));
    const iso = d.toISOString().slice(0, 10);
    const rec = history.find((h) => h.date === iso); // { date, mood } | undefined
    return { iso, day: DAY_SHORT[d.getDay()].charAt(0), rec };
  });

  const hasPastData = history.length > 1;

  return (
    <div className="rounded-3xl glass petal-shadow animate-pop-in overflow-hidden">
      {/* Header row */}
      <div className="px-4 pt-4 pb-3 sm:px-6 sm:pt-5">
        <div className="flex items-start justify-between gap-2 mb-4">
          <div>
            <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground/70 mb-0.5">
              {greeting()}
            </p>
            <h3 className="font-headline text-base sm:text-lg font-semibold text-foreground/90 leading-snug">
              How are you feeling today?
            </h3>
          </div>
          {streak >= 2 && (
            <div className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-primary/10 border border-primary/20">
              <span className="text-[11px] font-semibold text-primary">{streak} day streak</span>
            </div>
          )}
        </div>

        {/* Mood picker */}
        <div className="grid grid-cols-5 gap-2 sm:gap-3">
          {MOODS.map(({ key, label, color, bg, border }) => {
            const active = selected === key;
            return (
              <button
                key={key}
                type="button"
                onClick={() => pick(key)}
                aria-label={label}
                aria-pressed={active}
                className={cn(
                  "flex flex-col items-center gap-1.5 py-2.5 px-1 rounded-2xl border transition-all duration-300",
                  "hover:-translate-y-0.5 hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  active
                    ? "shadow-md scale-[1.04]"
                    : "border-border/40 bg-card/40 hover:bg-card/70"
                )}
                style={active ? { background: bg, borderColor: border } : {}}
              >
                <MoodFace
                  mood={key}
                  className={cn(
                    "h-7 w-7 sm:h-8 sm:w-8 transition-all duration-300",
                    active ? "scale-110" : ""
                  )}
                  style={active ? { color } : {}}
                />
                <span
                  className="text-[10px] sm:text-[11px] font-medium leading-none"
                  style={{ color: active ? color : undefined }}
                >
                  {label}
                </span>
              </button>
            );
          })}
        </div>

        {/* Affirmation card */}
        {selectedMood && (
          <div
            className="mt-3 rounded-2xl px-4 py-3 transition-all duration-300 animate-pop-in"
            style={{ background: selectedMood.bg, borderLeft: `3px solid ${selectedMood.color}` }}
          >
            <p className="text-sm font-medium leading-snug" style={{ color: selectedMood.color }}>
              {selectedMood.affirmation}
            </p>
            <p className="text-[12px] text-muted-foreground mt-1 leading-relaxed">
              {selectedMood.tip}
            </p>
          </div>
        )}
      </div>

      {/* History section */}
      {hasPastData && (
        <div className="border-t border-border/25">
          <button
            type="button"
            onClick={() => setShowHistory((v) => !v)}
            className="w-full flex items-center justify-between px-4 sm:px-6 py-2.5 text-left hover:bg-primary/5 transition-colors"
          >
            <span className="text-[11px] uppercase tracking-wider text-muted-foreground/60 font-medium">
              Mood history · last 14 days
            </span>
            <svg
              width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
              className={cn("text-muted-foreground/40 transition-transform duration-200", showHistory && "rotate-180")}
            >
              <path d="M6 9l6 6 6-6" />
            </svg>
          </button>

          {showHistory && (
            <div className="px-4 sm:px-6 pb-4 animate-pop-in">
              {/* Bar chart */}
              <div className="flex items-end gap-1 h-12 mb-1">
                {last14.map(({ iso, day, rec }) => {
                  const color = rec ? getMoodColor(rec.mood) : null;
                  return (
                    <Tooltip key={iso}>
                      <TooltipTrigger asChild>
                        <div className="flex-1 flex flex-col items-center gap-1 cursor-default">
                          <div
                            className="w-full rounded-full transition-all duration-500"
                            style={{
                              height: color ? "36px" : "6px",
                              backgroundColor: color ?? "hsl(var(--border))",
                              opacity: color ? 0.7 : 0.3,
                            }}
                          />
                          <span className="text-[8px] text-muted-foreground/40">{day}</span>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent side="top">
                        <span className="capitalize">{rec ? rec.mood : "no entry"}</span>
                        <span className="ml-1 text-muted-foreground text-[10px]">{iso}</span>
                      </TooltipContent>
                    </Tooltip>
                  );
                })}
              </div>

              {/* Legend */}
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
                {MOODS.map(({ key, label, color }) => (
                  <span key={key} className="flex items-center gap-1.5 text-[10px] text-muted-foreground/60">
                    <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
                    {label}
                  </span>
                ))}
              </div>

              {streak >= 2 && (
                <p className="mt-2 text-[11px] text-muted-foreground/50 text-center">
                  You have checked in {streak} days in a row. Keep going.
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
