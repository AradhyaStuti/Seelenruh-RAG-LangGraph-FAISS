import { useEffect, useRef, useState } from "react";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogTitle,
  AlertDialogDescription,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { BreathLungs, SoftClose } from "@/components/icons";
import { cn } from "@/lib/utils";

const PATTERNS = [
  {
    key: "calm",
    name: "Calm 4-6",
    description: "Slow exhale to settle a racing mind.",
    phases: [
      { label: "Inhale", seconds: 4 },
      { label: "Exhale", seconds: 6 },
    ],
  },
  {
    key: "box",
    name: "Box 4-4-4-4",
    description: "Used by athletes to steady focus before pressure.",
    phases: [
      { label: "Inhale", seconds: 4 },
      { label: "Hold", seconds: 4 },
      { label: "Exhale", seconds: 4 },
      { label: "Hold", seconds: 4 },
    ],
  },
  {
    key: "478",
    name: "4-7-8",
    description: "Helps with sleep and releasing tension.",
    phases: [
      { label: "Inhale", seconds: 4 },
      { label: "Hold", seconds: 7 },
      { label: "Exhale", seconds: 8 },
    ],
  },
];

export function BreathingCompanion({ open, onOpenChange }) {
  const [patternKey, setPatternKey] = useState("calm");
  const [running, setRunning] = useState(false);
  const [phaseIdx, setPhaseIdx] = useState(0);
  const [tick, setTick] = useState(0);
  const [cycles, setCycles] = useState(0);

  const intervalRef = useRef(null);
  const pattern = PATTERNS.find((p) => p.key === patternKey);
  const phase = pattern.phases[phaseIdx];

  useEffect(() => {
    if (!open) stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const start = () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    setRunning(true);
    setPhaseIdx(0);
    setTick(0);
    setCycles(0);

    let localPhase = 0;
    let localTick = 0;
    intervalRef.current = setInterval(() => {
      localTick += 1;
      if (localTick >= pattern.phases[localPhase].seconds) {
        localTick = 0;
        localPhase += 1;
        if (localPhase >= pattern.phases.length) {
          localPhase = 0;
          setCycles((c) => c + 1);
        }
        setPhaseIdx(localPhase);
      }
      setTick(localTick);
    }, 1000);
  };

  const stop = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setRunning(false);
    setPhaseIdx(0);
    setTick(0);
  };

  const remaining = Math.max(1, phase.seconds - tick);
  const scale = running
    ? phase.label === "Inhale"
      ? 1 + (tick / phase.seconds) * 0.5
      : phase.label === "Exhale"
      ? 1.5 - (tick / phase.seconds) * 0.5
      : 1.25
    : 1;

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-md rounded-3xl border-border/40 bg-card/85 backdrop-blur-xl petal-shadow p-0 overflow-hidden">
        <div className="relative">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="absolute right-3 top-3 z-10 h-8 w-8 rounded-full text-muted-foreground hover:bg-muted/60 hover:text-foreground transition flex items-center justify-center"
            aria-label="Close"
          >
            <SoftClose className="h-4 w-4" />
          </button>

          <div className="px-6 pt-6 pb-2 text-center">
            <AlertDialogTitle className="font-headline text-xl tracking-tight">
              Breathing
            </AlertDialogTitle>
            <AlertDialogDescription className="text-xs text-muted-foreground mt-1">
              {pattern.description}
            </AlertDialogDescription>
          </div>

          <div className="relative mx-auto my-2 h-56 w-56 flex items-center justify-center">
            <div
              className="absolute inset-0 rounded-full bg-gradient-to-br from-primary/30 via-accent/25 to-secondary/30 blur-2xl transition-transform duration-1000"
              style={{ transform: `scale(${scale})` }}
            />
            <div
              className="relative h-40 w-40 rounded-full bg-gradient-to-br from-primary/80 via-primary/50 to-accent/60 shadow-2xl transition-transform ease-in-out duration-1000 flex items-center justify-center"
              style={{ transform: `scale(${scale})` }}
            >
              <div className="text-center text-primary-foreground">
                <div className="text-[10px] uppercase tracking-[0.22em] opacity-80">
                  {running ? phase.label : "Ready"}
                </div>
                <div className="font-headline text-4xl font-light tabular-nums">
                  {running ? remaining : pattern.phases[0].seconds}
                </div>
              </div>
            </div>
          </div>

          <div className="px-6 pb-2 flex justify-center gap-1.5">
            {PATTERNS.map((p) => (
              <button
                key={p.key}
                type="button"
                onClick={() => {
                  setPatternKey(p.key);
                  if (running) stop();
                }}
                className={cn(
                  "px-3 py-1.5 rounded-full text-xs transition-all border",
                  patternKey === p.key
                    ? "bg-primary/15 border-primary/40 text-foreground"
                    : "bg-card/40 border-border/40 text-muted-foreground hover:text-foreground hover:border-primary/30"
                )}
              >
                {p.name}
              </button>
            ))}
          </div>

          <div className="px-6 pb-6 pt-4 flex items-center justify-center gap-3">
            <Button
              type="button"
              size="lg"
              onClick={running ? stop : start}
              className="rounded-full px-6 bg-gradient-to-br from-primary to-accent text-primary-foreground hover-lift petal-shadow"
            >
              <BreathLungs className="h-4 w-4 mr-2" />
              {running ? "Stop" : "Start"}
            </Button>
            {cycles > 0 && (
              <span className="text-xs text-muted-foreground">
                {cycles} {cycles === 1 ? "cycle" : "cycles"}
              </span>
            )}
          </div>
        </div>
      </AlertDialogContent>
    </AlertDialog>
  );
}
