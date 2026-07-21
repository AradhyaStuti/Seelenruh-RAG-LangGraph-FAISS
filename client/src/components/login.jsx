import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { BlossomLogo } from "@/components/icons";
import { login, signup } from "@/lib/auth";
import { cn } from "@/lib/utils";

function passwordStrength(pw) {
  if (!pw) return { score: 0, label: "" };
  let score = 0;
  if (pw.length >= 6) score += 1;
  if (pw.length >= 10) score += 1;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score += 1;
  if (/\d/.test(pw)) score += 1;
  if (/[^A-Za-z0-9]/.test(pw)) score += 1;
  const labels = ["", "Weak", "Fair", "Good", "Strong", "Very Strong"];
  return { score, label: labels[score] };
}

function EyeIcon({ open }) {
  return open ? (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
      <line x1="1" y1="1" x2="23" y2="23"/>
    </svg>
  ) : (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
      <circle cx="12" cy="12" r="3"/>
    </svg>
  );
}

export function LoginScreen() {
  const [mode, setMode] = useState("login"); // "login" | "signup"
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [capsLock, setCapsLock] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const firstFieldRef = useRef(null);

  useEffect(() => {
    setError("");
    const t = window.setTimeout(() => firstFieldRef.current?.focus(), 80);
    return () => window.clearTimeout(t);
  }, [mode]);

  const handlePwKey = (e) => {
    if (typeof e.getModifierState === "function") setCapsLock(e.getModifierState("CapsLock"));
  };

  const submit = async (e) => {
    e.preventDefault();
    if (loading) return;
    setError("");
    setLoading(true);
    try {
      if (mode === "signup") {
        await signup({ email, name, password });
      } else {
        await login({ email, password });
      }
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const strength = passwordStrength(password);

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 bg-background">
      <div className="w-full max-w-sm">

        {/* Brand mark */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center h-14 w-14 rounded-3xl bg-gradient-to-br from-primary/20 via-card to-accent/15 ring-1 ring-primary/25 petal-shadow mb-4 mx-auto">
            <BlossomLogo className="h-7 w-7" />
          </div>
          <h1 className="font-headline text-2xl font-bold tracking-tight text-foreground">
            Seelen<span className="text-gradient font-bold">ruh</span>
          </h1>
          <p className="text-sm text-muted-foreground mt-1">Wellbeing, rights, and safety — one place.</p>
        </div>

        {/* Card */}
        <div className="rounded-3xl glass-strong petal-shadow border border-border/40 overflow-hidden">
          <div className="px-6 pt-6 pb-1">
            <h2 className="font-headline text-lg font-semibold text-foreground">
              {mode === "signup" ? "Create your account" : "Welcome back"}
            </h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              {mode === "signup" ? "Your information is kept private." : "Sign in to continue."}
            </p>
          </div>

          <div className="px-6 pb-6">
            <form onSubmit={submit} className="space-y-4 mt-5" autoComplete="on">

              {/* Name — signup only */}
              {mode === "signup" && (
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-foreground">Full Name</label>
                  <Input
                    ref={firstFieldRef}
                    type="text"
                    placeholder="Your name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    minLength={1}
                    maxLength={80}
                    autoComplete="name"
                    className="h-10 rounded-xl border-border/60 focus-visible:border-primary/60 focus-visible:ring-primary/20 bg-background/60 text-foreground placeholder:text-muted-foreground/50"
                  />
                </div>
              )}

              {/* Email */}
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">Email Address</label>
                <Input
                  ref={mode === "login" ? firstFieldRef : undefined}
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                  className="h-10 rounded-xl border-border/60 focus-visible:border-primary/60 focus-visible:ring-primary/20 bg-background/60 text-foreground placeholder:text-muted-foreground/50"
                />
              </div>

              {/* Password */}
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">Password</label>
                <div className="relative">
                  <Input
                    type={showPassword ? "text" : "password"}
                    placeholder={mode === "signup" ? "Minimum 6 characters" : "Your password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onKeyUp={handlePwKey}
                    onKeyDown={handlePwKey}
                    required
                    minLength={6}
                    autoComplete={mode === "login" ? "current-password" : "new-password"}
                    className="h-10 rounded-xl border-border/60 focus-visible:border-primary/60 focus-visible:ring-primary/20 bg-background/60 text-foreground placeholder:text-muted-foreground/50 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    tabIndex={-1}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground/60 hover:text-muted-foreground transition-colors"
                  >
                    <EyeIcon open={showPassword} />
                  </button>
                </div>
              </div>

              {/* Password strength + caps lock */}
              {(capsLock || (mode === "signup" && password)) && (
                <div className="flex items-center justify-between gap-3">
                  {capsLock ? (
                    <span className="text-xs text-amber-600 font-medium">Caps Lock is on</span>
                  ) : <span />}
                  {mode === "signup" && password && (
                    <div className="flex items-center gap-2 ml-auto">
                      <div className="flex gap-1">
                        {[1, 2, 3, 4].map((i) => (
                          <span
                            key={i}
                            className={cn(
                              "h-1.5 w-5 rounded-full transition-colors duration-300",
                              i <= strength.score
                                ? strength.score <= 2 ? "bg-amber-500" : "bg-emerald-500"
                                : "bg-border"
                            )}
                          />
                        ))}
                      </div>
                      <span className="text-xs text-muted-foreground">{strength.label}</span>
                    </div>
                  )}
                </div>
              )}

              {error && (
                <div role="alert" className="rounded-xl border border-destructive/25 bg-destructive/8 px-3 py-2.5 text-sm text-destructive animate-fade-in">
                  {error}
                </div>
              )}

              <Button
                type="submit"
                disabled={loading || !email || password.length < 6 || (mode === "signup" && !name)}
                className="w-full h-10 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 font-medium transition-all duration-200 petal-shadow disabled:opacity-50 disabled:shadow-none mt-2"
              >
                {loading && (
                  <span className="inline-block h-4 w-4 rounded-full border-2 border-primary-foreground/30 border-t-primary-foreground animate-spin mr-2" />
                )}
                {loading
                  ? (mode === "signup" ? "Creating account…" : "Signing in…")
                  : (mode === "signup" ? "Create account" : "Sign in")}
              </Button>

              <div className="text-center text-sm text-muted-foreground pt-1">
                {mode === "signup" ? "Already have an account?" : "Don't have an account?"}{" "}
                <button
                  type="button"
                  onClick={() => { setMode(mode === "signup" ? "login" : "signup"); setError(""); setShowPassword(false); }}
                  className="text-primary font-medium hover:text-primary/75 transition-colors focus:outline-none focus-visible:underline"
                >
                  {mode === "signup" ? "Sign in" : "Create account"}
                </button>
              </div>

            </form>
          </div>
        </div>

        <p className="text-center text-xs text-muted-foreground/55 mt-6 leading-relaxed">
          Seelenruh provides informational support only —<br className="hidden sm:inline" /> not a substitute for professional advice.
        </p>
      </div>
    </div>
  );
}
