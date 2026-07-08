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

          <div className="px-4 pb-4 max-h-[60vh] overflow-y-auto">
            {ordered.length === 0 ? (
              <div className="text-center py-10 px-4">
                <div className="mx-auto h-14 w-14 rounded-2xl bg-muted/50 flex items-center justify-center mb-3">
                  <BlossomLogo className="h-6 w-6 text-muted-foreground/60" />
                </div>
                <p className="text-sm text-foreground/80 font-medium">No chats with {persona} yet</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Anything you say will be saved here and you can come back to it later.
                </p>
              </div>
            ) : (
              <ul className="space-y-1.5">
                {ordered.map((s) => {
                  const isActive = s.id === activeId;
                  const turns = s.messages.filter((m) => m.role === "user").length;
                  return (
                    <li key={s.id}>
                      <div
                        className={cn(
                          "group flex items-start gap-2 rounded-2xl border p-3 transition-all",
                          isActive
                            ? "border-primary/45 bg-primary/10"
                            : "border-border/40 bg-card/60 hover:border-primary/40"
                        )}
                      >
                        <button
                          type="button"
                          onClick={() => {
                            onSelect(s.id);
                            onOpenChange(false);
                          }}
                          className="flex-1 text-left min-w-0"
                        >
                          <p className="text-sm text-foreground/90 font-medium leading-snug line-clamp-2">
                            {s.title || "New chat"}
                          </p>
                          <p className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground/70">
                            {formatDate(s.updatedAt)} · {turns} {turns === 1 ? "turn" : "turns"} · {domain}
                          </p>
                        </button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onDelete(s.id)}
                          className="h-7 text-xs text-muted-foreground hover:text-destructive opacity-60 group-hover:opacity-100 transition-opacity shrink-0"
                          aria-label="Delete chat"
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
