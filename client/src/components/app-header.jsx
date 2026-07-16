import { useEffect, useState, useRef, lazy, Suspense } from "react";
import { BlossomLogo, BreathLungs, HeartBookmark } from "@/components/icons";
import { LangToggle } from "@/components/lang-toggle";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { SavedMomentsDrawer } from "@/components/saved-moments";

const BreathingCompanion = lazy(() => import("@/components/breathing-companion").then(m => ({ default: m.BreathingCompanion })));
const SignOutDialog       = lazy(() => import("@/components/sign-out-dialog").then(m => ({ default: m.SignOutDialog })));
const ChangePasswordDialog = lazy(() => import("@/components/change-password").then(m => ({ default: m.ChangePasswordDialog })));
import { getUser, subscribe } from "@/lib/auth";
import { verifyAdminKey, setAdminKey } from "@/lib/adminApi";
import { cn } from "@/lib/utils";

function initialsOf(name, email) {
  const source = (name || email || "").trim();
  if (!source) return "?";
  const parts = source.split(/[\s@._-]+/).filter(Boolean);
  const letters = parts.slice(0, 2).map((p) => p[0]).join("");
  return (letters || source[0]).toUpperCase();
}

function AccountMenu({ user, onSignOut, onChangePassword }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label="Account menu"
            aria-expanded={open}
            className="ml-0.5 sm:ml-1 inline-flex h-10 w-10 sm:h-9 sm:w-9 items-center justify-center rounded-full bg-gradient-to-br from-primary/20 via-accent/15 to-secondary/20 ring-1 ring-primary/30 text-[13px] sm:text-xs font-semibold tracking-wide text-foreground/80 transition active:scale-95 hover:scale-105 hover:ring-primary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {initialsOf(user.name, user.email)}
          </button>
        </TooltipTrigger>
        <TooltipContent>
          {user.name || user.email} — account
          <span className="ml-2 text-[10px] opacity-70">⌘/Ctrl + ⇧ + Q</span>
        </TooltipContent>
      </Tooltip>

      {open && (
        <div
          className={cn(
            "absolute right-0 top-12 z-50 min-w-[200px] rounded-2xl border border-border/50 shadow-xl",
            "bg-card/95 backdrop-blur-md py-1.5 animate-in fade-in-0 zoom-in-95 slide-in-from-top-2 duration-150"
          )}
        >
          {/* User info */}
          <div className="px-4 py-2.5 border-b border-border/40">
            <p className="text-sm font-semibold truncate">{user.name || "Account"}</p>
            <p className="text-[11px] text-muted-foreground truncate">{user.email}</p>
          </div>

          {/* Actions */}
          <div className="py-1">
            <button
              type="button"
              onClick={() => { setOpen(false); onChangePassword(); }}
              className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-foreground/80 hover:bg-primary/8 hover:text-foreground transition-colors text-left"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
              Change password
            </button>
            <button
              type="button"
              onClick={() => { setOpen(false); onSignOut(); }}
              className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-foreground/80 hover:bg-primary/8 hover:text-foreground transition-colors text-left"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function AdminKeyDialog({ open, onClose, onSuccess }) {
  const [key, setKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    if (!key.trim()) return;
    setLoading(true);
    setError("");
    try {
      const ok = await verifyAdminKey(key.trim());
      if (ok) {
        setAdminKey(key.trim());
        onSuccess();
        setKey("");
      } else {
        setError("Invalid admin key.");
      }
    } catch {
      setError("Could not reach the server.");
    } finally {
      setLoading(false);
    }
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
      <div className="w-full max-w-sm mx-4 rounded-3xl border border-border/40 bg-card/95 backdrop-blur-xl petal-shadow p-6 space-y-4">
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-2xl bg-primary/10 flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-primary" aria-hidden="true" focusable="false">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold">Admin Access</p>
            <p className="text-[11px] text-muted-foreground">Enter your admin key to continue</p>
          </div>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          <Input
            type="password"
            placeholder="Admin key"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            autoFocus
            className="rounded-xl"
          />
          {error && <p className="text-[11px] text-red-500">{error}</p>}
          <div className="flex gap-2">
            <Button type="button" variant="ghost" onClick={onClose} className="flex-1 rounded-xl" disabled={loading}>
              Cancel
            </Button>
            <Button type="submit" className="flex-1 rounded-xl" disabled={loading || !key.trim()}>
              {loading ? "Checking…" : "Enter"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function AppHeader({ onAdminClick }) {
  const [breatheOpen, setBreatheOpen] = useState(false);
  const [savedOpen, setSavedOpen] = useState(false);
  const [signOutOpen, setSignOutOpen] = useState(false);
  const [changePwOpen, setChangePwOpen] = useState(false);
  const [adminKeyOpen, setAdminKeyOpen] = useState(false);
  const [user, setUser] = useState(() => getUser());

  useEffect(() => subscribe(() => setUser(getUser())), []);

  useEffect(() => {
    function onKey(e) {
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.shiftKey && (e.key === "Q" || e.key === "q")) {
        e.preventDefault();
        if (getUser()) setSignOutOpen(true);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      <header className="w-full max-w-5xl mx-auto flex items-center justify-between gap-2 px-3 sm:px-6 py-3 sm:py-5">
        <div className="group flex min-w-0 items-center gap-2 sm:gap-3 cursor-default">
          <div className="relative shrink-0">
            <div className="h-10 w-10 sm:h-12 sm:w-12 rounded-3xl bg-gradient-to-br from-card via-card/90 to-primary/10 ring-1 ring-primary/25 petal-shadow flex items-center justify-center transition-all duration-300 group-hover:scale-105 group-hover:ring-primary/45">
              <BlossomLogo className="h-6 w-6 sm:h-7 sm:w-7" />
            </div>
          </div>
          <div className="min-w-0 leading-tight">
            <p className="font-headline text-base sm:text-xl font-semibold tracking-tight truncate">
              Seelen<span className="text-gradient font-bold">ruh</span>
            </p>
            <p className="text-[10px] sm:text-xs text-muted-foreground truncate max-w-[44vw] sm:max-w-none">
              {user?.name ? `Hi, ${user.name}` : "peace of the soul"}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-0.5 sm:gap-1.5">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setAdminKeyOpen(true)}
                aria-label="Admin panel"
                className="rounded-full hover:bg-primary/10 hover:text-primary transition opacity-40 hover:opacity-100"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14" />
                </svg>
              </Button>
            </TooltipTrigger>
            <TooltipContent>Admin panel</TooltipContent>
          </Tooltip>
          <LangToggle />

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setBreatheOpen(true)}
                aria-label="Breathing"
                className="rounded-full hover:bg-primary/10 hover:text-primary transition"
              >
                <BreathLungs className="h-5 w-5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Breathing</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setSavedOpen(true)}
                aria-label="Saved messages"
                className="rounded-full hover:bg-primary/10 hover:text-primary transition"
              >
                <HeartBookmark className="h-5 w-5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Saved</TooltipContent>
          </Tooltip>

          {user && (
            <AccountMenu
              user={user}
              onSignOut={() => setSignOutOpen(true)}
              onChangePassword={() => setChangePwOpen(true)}
            />
          )}
        </div>
      </header>

      <Suspense fallback={null}>
        {breatheOpen && <BreathingCompanion open={breatheOpen} onOpenChange={setBreatheOpen} />}
        {savedOpen   && <SavedMomentsDrawer open={savedOpen}   onOpenChange={setSavedOpen}   />}
        {signOutOpen && <SignOutDialog      open={signOutOpen} onOpenChange={setSignOutOpen} user={user} />}
        {changePwOpen && <ChangePasswordDialog open={changePwOpen} onOpenChange={setChangePwOpen} />}
      </Suspense>
      <AdminKeyDialog
        open={adminKeyOpen}
        onClose={() => setAdminKeyOpen(false)}
        onSuccess={() => { setAdminKeyOpen(false); onAdminClick?.(); }}
      />
    </>
  );
}
