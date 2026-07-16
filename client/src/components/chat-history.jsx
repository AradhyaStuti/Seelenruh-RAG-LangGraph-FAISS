import { useMemo } from "react";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogTitle,
  AlertDialogDescription,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { SoftClose, SoftRefresh, BlossomLogo } from "@/components/icons";
import { cn } from "@/lib/utils";

function formatDate(ts) {
  const d = new Date(ts);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function ChatHistoryDrawer({
  open,
  onOpenChange,
  persona,
  domain,
  sessions,
  activeId,
  onSelect,
  onDelete,
  onNew,
}) {
  const ordered = useMemo(
    () => [...sessions].sort((a, b) => b.updatedAt - a.updatedAt),
    [sessions]
  );

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
                <BlossomLogo className="h-5 w-5" />
              </div>
              <div>
                <AlertDialogTitle className="font-headline text-lg tracking-tight">
                  {persona}'s past chats
                </AlertDialogTitle>
                <AlertDialogDescription className="text-xs text-muted-foreground">
                  Stored on this device only · {ordered.length} {ordered.length === 1 ? "chat" : "chats"}
                </AlertDialogDescription>
              </div>
            </div>

            <div className="mt-3 flex justify-end">
              <Button
                size="sm"
                onClick={() => {
                  onNew();
                  onOpenChange(false);
                }}
                className="h-8 rounded-full text-xs gap-1.5 bg-gradient-to-br from-primary to-primary/85 text-primary-foreground"
              >
                <SoftRefresh className="h-3.5 w-3.5" />
                New chat
              </Button>
            </div>
          </div>

          <div
            className="px-4 pb-4 max-h-[65vh] overflow-y-auto overscroll-contain"
            role="region"
            aria-label="Chat history list"
          >
            {ordered.length === 0 ? (
              <div className="text-center py-12 px-4">
                <div className="mx-auto h-14 w-14 rounded-2xl bg-muted/40 flex items-center justify-center mb-4">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-muted-foreground/50" aria-hidden>
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                  </svg>
                </div>
                <p className="text-sm text-foreground/75 font-medium">No chats with {persona} yet</p>
                <p className="text-xs text-muted-foreground/65 mt-1 leading-relaxed max-w-[220px] mx-auto">
                  Start a conversation — it will appear here so you can return to it later.
                </p>
              </div>
            ) : (
              <ul className="space-y-1.5" role="listbox" aria-label={`${persona}'s conversations`}>
                {ordered.map((s) => {
                  const isActive = s.id === activeId;
                  const turns = s.messages.filter((m) => m.role === "user").length;
                  const title = s.title || "New chat";
                  return (
                    <li key={s.id} role="option" aria-selected={isActive}>
                      <div
                        className={cn(
                          "group flex items-start gap-2 rounded-2xl border p-3 transition-all duration-150",
                          isActive
                            ? "border-primary/45 bg-primary/10"
                            : "border-border/40 bg-card/60 hover:border-primary/35 hover:bg-card/80"
                        )}
                      >
                        <button
                          type="button"
                          onClick={() => {
                            onSelect(s.id);
                            onOpenChange(false);
                          }}
                          aria-label={`Open chat: ${title}${isActive ? " (current)" : ""}`}
                          className="flex-1 text-left min-w-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 rounded-lg"
                        >
                          <p className="text-sm text-foreground/90 font-medium leading-snug line-clamp-2">
                            {title}
                          </p>
                          <p className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground/60">
                            {formatDate(s.updatedAt)} · {turns} {turns === 1 ? "turn" : "turns"}
                          </p>
                        </button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onDelete(s.id)}
                          className="h-8 min-w-[44px] text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/8 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-all duration-150 shrink-0"
                          aria-label={`Delete chat: ${title}`}
                        >
                          Delete
                        </Button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      </AlertDialogContent>
    </AlertDialog>
  );
}
