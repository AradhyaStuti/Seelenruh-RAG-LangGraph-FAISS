import { useEffect, useMemo, useState } from "react";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogTitle,
  AlertDialogDescription,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SoftUser } from "@/components/icons";
import { clearAuth, deleteAccount } from "@/lib/auth";
import { downloadExport } from "@/lib/export";
import { useToast } from "@/hooks/use-toast";

export function SignOutDialog({ open, onOpenChange, user }) {
  const [wipe, setWipe] = useState(false);
  const [danger, setDanger] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [busy, setBusy] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    if (open) {
      setWipe(false);
      setDanger(false);
      setConfirmText("");
      setBusy(false);
    }
  }, [open]);

  const expectedConfirm = useMemo(
    () => (user?.email || "").trim().toLowerCase(),
    [user]
  );
  const confirmMatches =
    !!expectedConfirm && confirmText.trim().toLowerCase() === expectedConfirm;

  if (!user) return null;

  const handleSignOut = () => {
    clearAuth({ wipeUserData: wipe });
    onOpenChange(false);
    toast({
      title: "Signed out",
      description: wipe
        ? "Your data on this device was cleared. Take care."
        : "You're signed out. Your chats are still here when you come back.",
    });
  };

  const handleExport = () => {
    try {
      downloadExport();
      toast({
        title: "Export started",
        description: "Your JSON file is downloading. Keep it somewhere safe.",
      });
    } catch (err) {
      toast({
        title: "Couldn't export",
        description: err?.message || "Something went wrong preparing the file.",
        variant: "destructive",
      });
    }
  };

  const handleDelete = async () => {
    if (!confirmMatches || busy) return;
    setBusy(true);
    try {
      await deleteAccount();
      clearAuth({ wipeUserData: true });
      onOpenChange(false);
      toast({
        title: "Account deleted",
        description: "Your account and chats were removed. Be well.",
      });
    } catch (err) {
      setBusy(false);
      toast({
        title: "Couldn't delete account",
        description: err?.message || "Try again in a moment.",
        variant: "destructive",
      });
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="w-[calc(100vw-1.5rem)] max-w-md gap-3 rounded-2xl border-primary/15 bg-card p-5 sm:p-6 max-h-[92vh] overflow-y-auto">
        <div className="flex items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary/10 ring-1 ring-primary/25">
            <SoftUser className="h-6 w-6 text-primary" />
          </div>
          <div className="min-w-0 flex-1">
            <AlertDialogTitle className="font-headline text-base sm:text-lg">
              {user.name || "Your account"}
            </AlertDialogTitle>
            {user.email && (
              <p className="truncate text-xs text-muted-foreground">{user.email}</p>
            )}
          </div>
        </div>

        {!danger ? (
          <>
            <AlertDialogDescription className="text-[13px] leading-relaxed text-muted-foreground sm:text-sm">
              Signing out keeps your chats, mood trail, and saved messages on this device so they're
              waiting when you come back. On a shared device, tick the box below to wipe them.
            </AlertDialogDescription>

            <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-input/60 bg-background/60 px-3 py-3 text-sm transition active:bg-accent/40 hover:bg-accent/30 min-h-[52px]">
              <input
                type="checkbox"
                checked={wipe}
                onChange={(e) => setWipe(e.target.checked)}
                className="mt-0.5 h-5 w-5 cursor-pointer accent-primary"
              />
              <span className="leading-tight">
                Also clear my chats, mood trail and saved messages on this device.
                <span className="mt-0.5 block text-[11px] text-muted-foreground">
                  Your account stays — this only wipes local data.
                </span>
              </span>
            </label>

            <button
              type="button"
              onClick={handleExport}
              className="flex w-full items-center justify-between gap-3 rounded-xl border border-input/60 bg-background/60 px-3 py-3 text-left text-sm transition hover:bg-accent/30 active:bg-accent/40 min-h-[52px]"
            >
              <span className="leading-tight">
                Export my data
                <span className="mt-0.5 block text-[11px] text-muted-foreground">
                  Download a JSON of your chats, saved messages and mood trail.
                </span>
              </span>
              <span aria-hidden className="text-base text-muted-foreground">↓</span>
            </button>

            <div className="flex flex-col-reverse gap-2 pt-1 sm:flex-row sm:justify-between sm:pt-2">
              <button
                type="button"
                onClick={() => setDanger(true)}
                className="text-[13px] font-medium text-destructive/90 underline-offset-2 hover:underline sm:self-center"
              >
                Delete account…
              </button>
              <div className="flex flex-col-reverse gap-2 sm:flex-row">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => onOpenChange(false)}
                  className="h-11 w-full rounded-full sm:h-10 sm:w-auto"
                >
                  Stay signed in
                </Button>
                <Button
                  type="button"
                  variant={wipe ? "destructive" : "default"}
                  onClick={handleSignOut}
                  className="h-11 w-full rounded-full sm:h-10 sm:w-auto"
                >
                  {wipe ? "Sign out & clear data" : "Sign out"}
                </Button>
              </div>
            </div>
          </>
        ) : (
          <>
            <AlertDialogDescription className="text-[13px] leading-relaxed text-destructive/90 sm:text-sm">
              This permanently deletes your account and every chat saved on the server. Local data on
              this device is wiped too. This can't be undone — consider exporting first.
            </AlertDialogDescription>

            <div className="space-y-1.5">
              <label htmlFor="confirm-email" className="text-xs text-muted-foreground">
                Type <span className="font-mono text-foreground/80">{user.email}</span> to confirm
              </label>
              <Input
                id="confirm-email"
                type="email"
                autoComplete="off"
                autoFocus
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                placeholder={user.email}
                className="h-11 rounded-lg"
              />
            </div>

            <div className="flex flex-col-reverse gap-2 pt-1 sm:flex-row sm:justify-end sm:pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setDanger(false)}
                disabled={busy}
                className="h-11 w-full rounded-full sm:h-10 sm:w-auto"
              >
                Back
              </Button>
              <Button
                type="button"
                variant="destructive"
                onClick={handleDelete}
                disabled={!confirmMatches || busy}
                className="h-11 w-full rounded-full sm:h-10 sm:w-auto"
              >
                {busy ? "Deleting…" : "Delete forever"}
              </Button>
            </div>
          </>
        )}
      </AlertDialogContent>
    </AlertDialog>
  );
}
