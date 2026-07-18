/**
 * Admin API client — all calls include the X-Admin-Key header.
 * The key is stored in sessionStorage (cleared on tab close).
 */

const ADMIN_KEY_SESSION = "seelenruh:adminKey";

export function getAdminKey() {
  return sessionStorage.getItem(ADMIN_KEY_SESSION) ?? "";
}

export function setAdminKey(key) {
  if (key) sessionStorage.setItem(ADMIN_KEY_SESSION, key);
  else sessionStorage.removeItem(ADMIN_KEY_SESSION);
}

export function clearAdminKey() {
  sessionStorage.removeItem(ADMIN_KEY_SESSION);
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function adminHeaders(key) {
  return { "X-Admin-Key": key || getAdminKey() };
}

async function adminGet(path, params = {}) {
  const url = new URL(path, window.location.origin);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) url.searchParams.set(k, v);
  });
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30_000);
  let res;
  try {
    res = await fetch(url.toString(), {
      headers: adminHeaders(),
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timer);
    if (err?.name === "AbortError") throw new Error("Request timed out.");
    throw new Error("Can't reach the server.");
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 401) throw new Error("Invalid admin key.");
  if (res.status === 503) throw new Error("Admin endpoints are disabled on the server.");
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.detail || `Request failed (HTTP ${res.status})`);
  }
  return res.json();
}

async function adminPost(path, body = {}, params = {}) {
  const url = new URL(path, window.location.origin);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) url.searchParams.set(k, v);
  });
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 60_000);
  let res;
  try {
    res = await fetch(url.toString(), {
      method: "POST",
      headers: { "Content-Type": "application/json", ...adminHeaders() },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timer);
    if (err?.name === "AbortError") throw new Error("Request timed out.");
    throw new Error("Can't reach the server.");
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 401) throw new Error("Invalid admin key.");
  if (res.status === 503) throw new Error("Admin endpoints are disabled on the server.");
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.detail || `Request failed (HTTP ${res.status})`);
  }
  return res.json();
}

async function adminDelete(path, body = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30_000);
  let res;
  try {
    res = await fetch(path, {
      method: "DELETE",
      headers: { "Content-Type": "application/json", ...adminHeaders() },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timer);
    if (err?.name === "AbortError") throw new Error("Request timed out.");
    throw new Error("Can't reach the server.");
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 401) throw new Error("Invalid admin key.");
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.detail || `Request failed (HTTP ${res.status})`);
  }
  return res.json();
}

async function adminPatch(path, body = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30_000);
  let res;
  try {
    res = await fetch(path, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...adminHeaders() },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timer);
    if (err?.name === "AbortError") throw new Error("Request timed out.");
    throw new Error("Can't reach the server.");
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 401) throw new Error("Invalid admin key.");
  if (res.status === 404) throw new Error("Item not found.");
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.detail || `Request failed (HTTP ${res.status})`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Exported API functions
// ---------------------------------------------------------------------------

/** Verify that the provided key is valid by hitting /api/admin/status. */
export async function verifyAdminKey(key) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10_000);
  try {
    const res = await fetch("/api/admin/status", {
      headers: { "X-Admin-Key": key },
      signal: controller.signal,
    });
    if (res.status === 401 || res.status === 503) return false;
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

// Analytics & Status
export const fetchAdminAnalytics = () => adminGet("/api/admin/analytics");
export const fetchAdminStatus = () => adminGet("/api/admin/status");

// Knowledge Chunks
export const fetchChunks = (domain, page = 1, pageSize = 50) =>
  adminGet("/api/admin/chunks", { domain: domain || undefined, page, page_size: pageSize });

export const ingestChunks = (chunks) => adminPost("/api/admin/ingest", { chunks });

export const deleteChunks = (ids) => adminDelete("/api/admin/ingest", { ids });

// Documents
export const fetchDocuments = (domain, status) =>
  adminGet("/api/admin/documents", { domain: domain || undefined, status: status || undefined });

export const fetchDocument = (docId) => adminGet(`/api/admin/documents/${docId}`);

export const deleteDocument = (docId, hard = false) =>
  adminDelete(`/api/admin/documents/${docId}${hard ? "?hard=true" : ""}`, {});

export const restoreDocument = (docId) => adminPost(`/api/admin/documents/${docId}/restore`);

export async function uploadDocument(file, domain, topic, source) {
  const url = new URL("/api/admin/ingest-document", window.location.origin);
  url.searchParams.set("domain", domain);
  if (topic) url.searchParams.set("topic", topic);
  if (source) url.searchParams.set("source", source);

  const form = new FormData();
  form.append("file", file);

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 120_000); // 2 min for large files
  let res;
  try {
    res = await fetch(url.toString(), {
      method: "POST",
      headers: adminHeaders(),
      body: form,
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timer);
    if (err?.name === "AbortError") throw new Error("Upload timed out.");
    throw new Error("Can't reach the server.");
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 401) throw new Error("Invalid admin key.");
  if (res.status === 413) throw new Error("File too large (max 10 MB).");
  if (res.status === 415) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d?.detail || "Unsupported file type.");
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.detail || `Upload failed (HTTP ${res.status})`);
  }
  return res.json();
}

// Knowledge Gaps
export const fetchKnowledgeGaps = (status) =>
  adminGet("/api/admin/knowledge-gaps", { status: status || undefined });

export const updateKnowledgeGap = (gapId, status) =>
  adminPatch(`/api/admin/knowledge-gaps/${gapId}`, { status });

// Index Management
export const fetchSnapshots = () => adminGet("/api/admin/snapshots");

export const rollbackIndex = (steps = 1) =>
  adminPost("/api/admin/rollback", {}, { steps });

// Crawler
export const fetchCrawlerSources = () => adminGet("/api/admin/crawler/sources");
export const triggerCrawler = () => adminPost("/api/admin/crawler/trigger");

// Audit Log
export const fetchAuditLog = (limit = 100) =>
  adminGet("/api/admin/audit", { limit });
