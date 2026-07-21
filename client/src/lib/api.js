import { getToken, clearAuth, silentRefresh } from "@/lib/auth";

// Prevent concurrent refresh storms: one in-flight refresh promise shared by all callers
let _refreshPromise = null;

async function _tryRefresh() {
  if (!_refreshPromise) {
    _refreshPromise = silentRefresh().finally(() => { _refreshPromise = null; });
  }
  return _refreshPromise;
}

function authHeaders() {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function post(path, body, { _retried = false, timeoutMs = 120000 } = {}) {
  let res;
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(body),
      signal: controller.signal,
    }).finally(() => clearTimeout(timer));
  } catch (err) {
    if (err?.name === "AbortError") throw new Error("Request timed out. The server is taking too long — please try again.");
    throw new Error("Can't reach the server. Please check your connection.");
  }
  if (res.status === 401) {
    if (!_retried) {
      const refreshed = await _tryRefresh();
      if (refreshed) return post(path, body, { _retried: true });
    }
    clearAuth();
    throw new Error("Your session expired. Please sign in again.");
  }
  if (res.status === 403) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.detail || "Please verify your email before continuing.");
  }
  if (res.status === 429) {
    throw new Error("You're sending messages too fast. Please wait a moment and try again.");
  }
  const text = await res.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error(`Server returned an unexpected response (HTTP ${res.status}).`);
    }
  }
  if (!res.ok) {
    const msg = data?.detail || data?.error || `Request failed (HTTP ${res.status})`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  if (!data) throw new Error("Server returned an empty response.");
  return data;
}

async function get(path, { _retried = false, timeoutMs = 30000 } = {}) {
  let res;
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    res = await fetch(path, {
      headers: authHeaders(),
      signal: controller.signal,
    }).finally(() => clearTimeout(timer));
  } catch (err) {
    if (err?.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw new Error("Can't reach the server. Please check your connection.");
  }
  if (res.status === 401) {
    if (!_retried) {
      const refreshed = await _tryRefresh();
      if (refreshed) return get(path, { _retried: true });
    }
    clearAuth();
    throw new Error("Your session expired. Please sign in again.");
  }
  if (res.status === 429) {
    throw new Error("Too many requests. Please wait a moment.");
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    let data = null;
    try { data = JSON.parse(text); } catch { /* ignore */ }
    const msg = data?.detail || data?.error || `Request failed (HTTP ${res.status})`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return res.json();
}

export function processUserMessage(input) {
  return post("/api/chat", input);
}

// streams tokens via SSE, falls back to regular endpoint on error
export async function streamUserMessage(input, { onToken, timeoutMs = 60000 } = {}) {
  const token = getToken();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res;
  try {
    res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(input),
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timer);
    if (err?.name === "AbortError") throw new Error("Response timed out. Please try again.");
    // Network error — fall back to regular endpoint
    return processUserMessage(input);
  }
  // Do NOT clear the timer here — keep it running to abort stalled stream reads too
  if (res.status === 401) {
    const refreshed = await _tryRefresh();
    if (refreshed) return streamUserMessage(input, { onToken });
    clearAuth();
    throw new Error("Your session expired. Please sign in again.");
  }
  if (res.status === 429) throw new Error("You're sending messages too fast. Please wait a moment and try again.");
  if (!res.ok) return processUserMessage(input);

  const reader = res.body?.getReader();
  if (!reader) return processUserMessage(input);

  const decoder = new TextDecoder();
  let buffer = "";
  let finalMeta = null;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        let event;
        try { event = JSON.parse(line.slice(6)); } catch { continue; }
        if (event.error) throw new Error(event.error);
        if (event.done) {
          finalMeta = event;
        } else if (event.token) {
          onToken?.(event.token);
        }
      }
    }
  } finally {
    clearTimeout(timer);
    reader.releaseLock();
  }

  return finalMeta || {};
}

export function matchSchemes(input) {
  return post("/api/schemes/match", input);
}

export function summarizeConversation(messages, opts = {}) {
  return post("/api/summary", {
    messages,
    persona: opts.persona,
    sessionId: opts.sessionId,
  });
}

export async function fetchAllSummaries(signal) {
  const token = getToken();
  if (!token) return { summaries: [] };
  // 10-second timeout so a slow server doesn't block app hydration
  const controller = new AbortController();
  const tid = setTimeout(() => controller.abort(), 10_000);
  // If the caller passes its own abort signal, forward it to our controller
  if (signal) {
    signal.addEventListener("abort", () => controller.abort(), { once: true });
  }
  try {
    const res = await fetch("/api/summary/all", {
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    });
    if (!res.ok) return { summaries: [] };
    return await res.json();
  } catch {
    return { summaries: [] };
  } finally {
    clearTimeout(tid);
  }
}

export function changePassword(currentPassword, newPassword) {
  return post("/api/auth/change-password", { currentPassword, newPassword });
}

// accepts .txt, .md, .csv, .json, .pdf, .docx (max 5 MB)
export async function parseDocument(file) {
  const token = getToken();
  const form = new FormData();
  form.append("file", file);
  let res;
  try {
    res = await fetch("/api/parse-document", {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
  } catch {
    throw new Error("Can't reach the server. Please check your connection.");
  }
  if (res.status === 401) {
    clearAuth();
    throw new Error("Your session expired. Please sign in again.");
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.detail || `Upload failed (HTTP ${res.status})`);
  }
  return res.json();
}

/** Fire-and-forget feedback — never throws so localStorage stays as primary. */
export async function submitFeedbackToServer(messageId, vote, domain, extra = {}) {
  try {
    await post("/api/feedback", { messageId, vote, domain, ...extra });
  } catch {
    // localStorage is the primary store; server sync is best-effort
  }
}

// returns { online, dbConnected } — dbConnected=false means in-memory fallback
export async function checkServerHealth() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 5000);
  try {
    const res = await fetch("/api/health", { signal: controller.signal });
    clearTimeout(timer);
    if (!res.ok) return { online: false, dbConnected: true };
    const data = await res.json().catch(() => ({}));
    return { online: true, dbConnected: data.dbConnected !== false };
  } catch {
    clearTimeout(timer);
    return { online: false, dbConnected: true };
  }
}

/**
 * Fetch server-stored message history for a session.
 * Returns [] when MongoDB is not connected or session has no stored messages.
 */
export async function fetchSessionHistory(sessionId) {
  if (!sessionId) return [];
  try {
    const data = await get(`/api/chat/history/${encodeURIComponent(sessionId)}`);
    return Array.isArray(data?.messages) ? data.messages : [];
  } catch {
    return [];
  }
}

export function buildHistory(messages, n = 6) {
  return messages
    .slice(1)
    .slice(-n)
    .map((m) => ({ role: m.role, content: m.content }));
}

/**
 * Download a conversation export from the server.
 * @param {string} sessionId - The session to export.
 * @param {"json"|"md"|"txt"} format - Export format.
 */
export async function exportConversation(sessionId, format = "json") {
  const token = getToken();
  const res = await fetch(`/api/export/${encodeURIComponent(sessionId)}?format=${format}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (res.status === 401) {
    clearAuth();
    throw new Error("Session expired. Please sign in again.");
  }
  if (res.status === 404) throw new Error("No conversation history found for this session.");
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.detail || "Export failed.");
  }
  const blob = await res.blob();
  const ext = format === "json" ? "json" : format === "md" ? "md" : "txt";
  const filename = `seelenruh_${sessionId.slice(0, 16)}.${ext}`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
