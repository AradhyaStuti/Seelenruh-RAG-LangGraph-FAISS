import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { login, signup, forgotPassword, resetPassword, verifyEmail } from "@/lib/auth";
import { cn } from "@/lib/utils";

// Modes: "login" | "signup" | "forgot" | "reset" | "verify"
// "reset" and "verify" are triggered when the URL has ?token=... query params.

function detectModeFromURL() {
  const params = new URLSearchParams(window.location.search);
  if (params.get("token") && window.location.pathname.includes("reset-password")) return "reset";
  if (params.get("token") && window.location.pathname.includes("verify-email")) return "verify";
  return "login";
}

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

function CheckIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12"/>
    </svg>
  );
}

export function LoginScreen() {
  const [mode, setMode] = useState(() => detectModeFromURL());
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [capsLock, setCapsLock] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const firstFieldRef = useRef(null);

  // Auto-run verify-email from URL token on mount
  useEffect(() => {
    if (mode === "verify") {
      const token = new URLSearchParams(window.location.search).get("token");
      if (token) handleVerifyToken(token);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    setError(""); setSuccess("");
    const t = window.setTimeout(() => firstFieldRef.current?.focus(), 80);
    return () => window.clearTimeout(t);
  }, [mode]);

  const handlePwKey = (e) => {
    if (typeof e.getModifierState === "function") setCapsLock(e.getModifierState("CapsLock"));
  };

  const handleVerifyToken = async (token) => {
    setLoading(true);
    try {
      await verifyEmail(token);
      setSuccess("Your email has been verified! You can now sign in.");
      setMode("login");
    } catch (err) {
      setError(err.message || "Verification link is invalid or has expired.");
    } finally {
      setLoading(false);
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    if (loading) return;
    setError(""); setSuccess("");
    setLoading(true);
    try {
      if (mode === "signup") {
        await signup({ email, name, password });
      } else if (mode === "login") {
        await login({ email, password });
      } else if (mode === "forgot") {
        await forgotPassword(email);
        setSuccess("Check your email — a reset link has been sent (or check the server console in dev mode).");
        setEmail("");
      } else if (mode === "reset") {
        const token = new URLSearchParams(window.location.search).get("token") || "";
        await resetPassword(token, password);
        setSuccess("Password updated! You can now sign in.");
        setMode("login");
        setPassword("");
      }
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const switchMode = () => {
    setError(""); setSuccess(""); setShowPassword(false);
    setMode(mode === "signup" ? "login" : "signup");
  };

  const strength = passwordStrength(password);

  const TITLES = {
    login: "Welcome to Seelenruh",
    signup: "Create your account",
    forgot: "Reset your password",
    reset: "Set a new password",
    verify: "Verifying your email…",
  };
  const SUBTITLES = {
    login: "Sign in to continue your session.",
    signup: "Your information is kept private and secure.",
    forgot: "Enter your email and we'll send a reset link.",
    reset: "Choose a new password for your account.",
    verify: "Please wait while we verify your email address.",
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-[#F8FAFC]">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="font-headline text-3xl font-semibold text-[#1E3A8A]">Seelenruh</h1>
          <p className="text-sm text-slate-500 mt-1">Peace of the Soul</p>
        </div>

        <Card className="border border-[#CBD5E1] shadow-sm rounded-lg bg-white">
          <CardHeader className="pb-4 pt-6 px-6">
            <h2 className="font-headline text-xl font-semibold text-[#0F172A]">{TITLES[mode]}</h2>
            <p className="text-sm text-slate-500 mt-1">{SUBTITLES[mode]}</p>
          </CardHeader>

          <CardContent className="px-6 pb-6">
            {/* Success banner */}
            {success && (
              <div className="mb-4 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2.5 text-sm text-emerald-700">
                <CheckIcon />
                {success}
              </div>
            )}

            {/* Verify-email loading state */}
            {mode === "verify" && loading && (
              <div className="flex items-center justify-center py-6 gap-3 text-slate-500 text-sm">
                <span className="inline-block h-5 w-5 rounded-full border-2 border-slate-300 border-t-[#1E3A8A] animate-spin" />
                Verifying…
              </div>
            )}

            {mode !== "verify" && (
              <form onSubmit={submit} className="space-y-4" autoComplete="on">
                {/* Name — signup only */}
                {mode === "signup" && (
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium text-[#0F172A]">Full Name</label>
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
                      className="h-10 rounded-lg border-[#CBD5E1] focus-visible:border-[#1E3A8A] focus-visible:ring-[#1E3A8A]/20 bg-white text-[#0F172A] placeholder:text-slate-400"
                    />
                  </div>
                )}

                {/* Email — login, signup, forgot */}
                {mode !== "reset" && (
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium text-[#0F172A]">Email Address</label>
                    <Input
                      ref={mode !== "signup" ? firstFieldRef : undefined}
                      type="email"
                      placeholder="you@example.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                      autoComplete="email"
                      className="h-10 rounded-lg border-[#CBD5E1] focus-visible:border-[#1E3A8A] focus-visible:ring-[#1E3A8A]/20 bg-white text-[#0F172A] placeholder:text-slate-400"
                    />
                  </div>
                )}

                {/* Password — login, signup, reset */}
                {mode !== "forgot" && (
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium text-[#0F172A]">
                      {mode === "reset" ? "New Password" : "Password"}
                    </label>
                    <div className="relative">
                      <Input
                        ref={mode === "reset" ? firstFieldRef : undefined}
                        type={showPassword ? "text" : "password"}
                        placeholder={mode === "signup" || mode === "reset" ? "Minimum 6 characters" : "Your password"}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        onKeyUp={handlePwKey}
                        onKeyDown={handlePwKey}
                        required
                        minLength={6}
                        autoComplete={mode === "login" ? "current-password" : "new-password"}
                        className="h-10 rounded-lg border-[#CBD5E1] focus-visible:border-[#1E3A8A] focus-visible:ring-[#1E3A8A]/20 bg-white text-[#0F172A] placeholder:text-slate-400 pr-10"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword((v) => !v)}
                        tabIndex={-1}
                        aria-label={showPassword ? "Hide password" : "Show password"}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                      >
                        <EyeIcon open={showPassword} />
                      </button>
                    </div>
                  </div>
                )}

                {/* Password hints */}
                {(capsLock || ((mode === "signup" || mode === "reset") && password)) && (
                  <div className="flex items-center justify-between gap-3">
                    {capsLock ? (
                      <span className="text-xs text-amber-600 font-medium">Caps Lock is on</span>
                    ) : <span />}
                    {(mode === "signup" || mode === "reset") && password && (
                      <div className="flex items-center gap-2 ml-auto">
                        <div className="flex gap-1">
                          {[1, 2, 3, 4].map((i) => (
                            <span
                              key={i}
                              className={cn(
                                "h-1.5 w-6 rounded-sm transition-colors",
                                i <= strength.score
                                  ? strength.score <= 2 ? "bg-amber-500" : "bg-emerald-600"
                                  : "bg-[#E2E8F0]"
                              )}
                            />
                          ))}
                        </div>
                        <span className="text-xs text-slate-500">{strength.label}</span>
                      </div>
                    )}
                  </div>
                )}

                {/* Forgot password link — login mode only */}
                {mode === "login" && (
                  <div className="text-right -mt-1">
                    <button
                      type="button"
                      onClick={() => setMode("forgot")}
                      className="text-xs text-[#1E3A8A] hover:underline focus:outline-none"
                    >
                      Forgot password?
                    </button>
                  </div>
                )}

                {error && (
                  <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700 animate-fade-in">
                    {error}
                  </div>
                )}

                <Button
                  type="submit"
                  disabled={
                    loading ||
                    (mode !== "reset" && !email) ||
                    (mode === "signup" && !name) ||
                    (mode !== "forgot" && password.length < 6)
                  }
                  className="w-full h-10 rounded-lg bg-[#1E3A8A] text-white hover:bg-[#1e3a8a]/90 font-medium transition-colors disabled:opacity-50 mt-2"
                >
                  {loading && (
                    <span className="inline-block h-4 w-4 rounded-full border-2 border-white/40 border-t-white animate-spin mr-2" />
                  )}
                  {loading
                    ? { login: "Signing in…", signup: "Creating account…", forgot: "Sending…", reset: "Updating…" }[mode]
                    : { login: "Sign in", signup: "Create account", forgot: "Send reset link", reset: "Set new password" }[mode]}
                </Button>

                {/* Bottom links */}
                <div className="flex items-center justify-between text-sm text-slate-500 pt-1">
                  {(mode === "login" || mode === "signup") ? (
                    <p>
                      {mode === "signup" ? "Already have an account?" : "Don't have an account?"}{" "}
                      <button type="button" onClick={switchMode} className="text-[#1E3A8A] font-medium hover:underline focus:outline-none">
                        {mode === "signup" ? "Sign in" : "Create account"}
                      </button>
                    </p>
                  ) : (
                    <button
                      type="button"
                      onClick={() => { setMode("login"); setError(""); setSuccess(""); }}
                      className="text-[#1E3A8A] font-medium hover:underline focus:outline-none text-sm"
                    >
                      ← Back to sign in
                    </button>
                  )}
                </div>
              </form>
            )}
          </CardContent>
        </Card>

        <p className="text-center text-xs text-slate-400 mt-6">
          Seelenruh provides informational support only — not a substitute for professional advice.
        </p>
      </div>
    </div>
  );
}
