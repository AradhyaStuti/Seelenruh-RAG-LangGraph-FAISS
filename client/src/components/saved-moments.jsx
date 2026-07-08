import { useEffect, useState } from "react";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogTitle,
  AlertDialogDescription,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { HeartBookmark, SoftClose, SoftCopy, SoftCheck } from "@/components/icons";

const STORAGE_KEY = "seelenruh:saved:v1";

export function loadMoments() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

export function saveMoment(m) {
  const existing = loadMoments();
  const moment = {
    ...m,
    id: crypto.randomUUID(),
    savedAt: Date.now(),
  };
  const next = [moment, ...existing].slice(0, 100);
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  return moment;
}

export function removeMoment(id) {
  const next = loadMoments().filter((m) => m.id !== id);
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
}

export function SavedMomentsDrawer({ open, onOpenChange, refreshKey }) {
  const [moments, setMoments] = useState([]);
  const [copiedId, setCopiedId] = useState(null);

  useEffect(() => {
    if (open) setMoments(loadMoments());
  }, [open, refreshKey]);

  const handleRemove = (id) => {
    removeMoment(id);
    setMoments(loadMoments());
  };

  const handleCopy = async (id, text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId((v) => (v === id ? null : v)), 1500);
    } catch {
      // ignore
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-lg rounded-3xl border-border/40 bg-card/85 backdrop-blur-xl petal-shadow p-0 overflow-hidden">
        <div className="relative">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="absolute right-3 top-3 z-10 h-8 w-8 rounded-full text-muted-foreground hover:bg-muted/60 hover:text-foreground transition flex items-center justify-center"
            aria-label="Close"
          >
            <SoftClose className="h-4 w-4" />
          </button>

          <div className="px-6 pt-6 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="h-10 w-10 rounded-2xl bg-primary/15 text-primary flex items-center justify-center">
                <HeartBookmark className="h-5 w-5" />
              </div>
              <div>
                <AlertDialogTitle className="font-headline text-lg tracking-tight">
                  Saved
                </AlertDialogTitle>
                <AlertDialogDescription className="text-xs text-muted-foreground">
                  Stored on this device only.
                </AlertDialogDescription>
              </div>
            </div>
          </div>

          <div className="px-4 pb-4 max-h-[60vh] overflow-y-auto">
            {moments.length === 0 ? (
              <div className="text-center py-10 px-4">
                <div className="mx-auto h-14 w-14 rounded-2xl bg-muted/50 flex items-center justify-center mb-3">
                  <HeartBookmark className="h-6 w-6 text-muted-foreground/60" />
                </div>
                <p className="text-sm text-foreground/80 font-medium">No saved messages yet</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Tap the heart on any reply to keep it here.
                </p>
              </div>
            ) : (
              <ul className="space-y-2.5">
                {moments.map((m) => (
                  <li
                    key={m.id}
                    className="group rounded-2xl border border-border/40 bg-card/60 p-3.5 hover:border-primary/40 transition-all"
                  >
                    <div className="flex items-start justify-between gap-2 mb-1.5">
                      <span className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-primary/80 font-medium">
                        <span className="h-1.5 w-1.5 rounded-full bg-primary/60" />
                        {m.persona} · {m.domain}
                      </span>
                      <span className="text-[10px] text-muted-foreground/70">
                        {new Date(m.savedAt).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                        })}
                      </span>
                    </div>
                    <p className="text-sm text-foreground/90 leading-relaxed whitespace-pre-wrap">
                      {m.content}
                    </p>
                    <div className="mt-2.5 flex items-center justify-end gap-1.5 opacity-60 group-hover:opacity-100 transition-opacity">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleCopy(m.id, m.content)}
                        className="h-7 text-xs gap-1"
                      >
                        {copiedId === m.id ? (
                          <>
                            <SoftCheck className="h-3.5 w-3.5 text-emerald-600" />
                            Copied
                          </>
                        ) : (
                          <>
                            <SoftCopy className="h-3.5 w-3.5" />
                            Copy
                          </>
                        )}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleRemove(m.id)}
                        className="h-7 text-xs text-muted-foreground hover:text-destructive"
                      >
                        Remove
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </AlertDialogContent>
    </AlertDialog>
  );
}
