import { useEffect, useState, useCallback } from "react";
import { checkServerHealth } from "@/lib/api";

const CHECK_INTERVAL_MS = 30_000;        // healthy polling: every 30s
const RETRY_WHEN_DOWN_MS = 5_000;        // aggressive retry when server is down
const RECHECK_AFTER_ONLINE_MS = 2_000;  // wait 2s after browser 'online' event then verify

// status values: "online" | "offline" | "server-down" | "db-warning" | "unknown"
export function OfflineBanner() {
  const [status, setStatus] = useState("unknown");

  const check = useCallback(async () => {
    if (!navigator.onLine) {
      setStatus("offline");
      return;
    }
    const { online, dbConnected } = await checkServerHealth();
    if (!online) {
      setStatus("server-down");
    } else if (!dbConnected) {
      setStatus("db-warning");
    } else {
      setStatus("online");
    }
  }, []);

  useEffect(() => {
    check();

    const handleOffline = () => setStatus("offline");
    const handleOnline = () => setTimeout(check, RECHECK_AFTER_ONLINE_MS);
    window.addEventListener("offline", handleOffline);
    window.addEventListener("online", handleOnline);

    const handleVisibility = () => { if (!document.hidden) check(); };
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener("online", handleOnline);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [check]);

  // Separate effect: retry aggressively when server is down, slow poll when healthy
  useEffect(() => {
    const interval = setInterval(() => {
      if (!document.hidden) check();
    }, status === "server-down" || status === "offline" ? RETRY_WHEN_DOWN_MS : CHECK_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [status, check]);

  if (status === "online" || status === "unknown") return null;

  const config = {
    "offline": {
      bg: "hsl(0 84% 60%)",
      msg: "No internet connection — check your network.",
      showRetry: true,
    },
    "server-down": {
      bg: "hsl(38 92% 50%)",
      msg: "Server is unreachable — responses will not work until it's back.",
      showRetry: true,
    },
    "db-warning": {
      bg: "hsl(220 80% 55%)",
      msg: "Database unavailable — running in limited mode. Sign-in and chat history may not be saved.",
      showRetry: false,
    },
  }[status];

  if (!config) return null;

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="fixed top-0 inset-x-0 z-50 flex items-center justify-center gap-2.5 px-4 py-2.5 text-sm font-medium shadow-lg transition-all duration-300"
      style={{ background: config.bg, color: "#fff" }}
    >
      <span
        className="inline-block h-2 w-2 rounded-full bg-white/70 animate-pulse shrink-0"
        aria-hidden
      />
      {config.msg}
      {config.showRetry && (
        <button
          type="button"
          onClick={check}
          className="ml-2 rounded-full px-3 py-0.5 text-xs font-semibold bg-white/20 hover:bg-white/30 transition"
        >
          Retry
        </button>
      )}
    </div>
  );
}
