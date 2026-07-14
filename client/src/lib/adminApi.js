/**
 * Admin API helpers.
 * All requests require an X-Admin-Key header which is stored in sessionStorage.
 */

const ADMIN_KEY_STORAGE = "seelenruh:admin-key";

export function getAdminKey() {
  try { return sessionStorage.getItem(ADMIN_KEY_STORAGE) || ""; } catch { return ""; }
}
export function setAdminKey(key) {
  try { sessionStorage.setItem(ADMIN_KEY_STORAGE, key); } catch {}
}
export function clearAdminKey() {
  try { sessionStorage.removeItem(ADMIN_KEY_STORAGE); } catch {}
}

function adminHeaders(extra = {}) {
  return { "X-Admin-Key": getAdminKey(), ...extra };
}

async function adminGet(path) {
  const res = await fetch(path, { headers: adminHeaders() });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

async function adminPost(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...adminHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

async function adminPatch(path, body) {
  const res = await fetch(path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...adminHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

async function adminDelete(path) {
  const res = await fetch(path, { method: "DELETE", headers: adminHeaders() });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ─── Verify admin key ─────────────────────────────────────────────────────────
export async function verifyAdminKey(key) {
  const res = await fetch("/api/admin/status", { headers: { "X-Admin-Key": key } });
  return res.ok;
}

// ─── Status & analytics ───────────────────────────────────────────────────────
export const fetchAdminStatus    = () => adminGet("/api/admin/status");
export const fetchAdminAnalytics = () => adminGet("/api/admin/analytics");
export const fetchAuditLog       = (limit = 100) => adminGet(`/api/admin/audit?limit=${limit}`);

// ─── Documents ────────────────────────────────────────────────────────────────
export const fetchDocuments = (params = {}) => {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString();
  return adminGet(`/api/admin/documents${qs ? "?" + qs : ""}`);
};
export const fetchDocument    = (docId) => adminGet(`/api/admin/documents/${docId}`);
export const deleteDocument   = (docId, hard = false) => adminDelete(`/api/admin/documents/${docId}?hard=${hard}`);
export const restoreDocument  = (docId) => adminPost(`/api/admin/documents/${docId}/restore`, {});

export async function uploadDocument(file, { domain, topic = "", source = "", language = "en" }, onProgress) {
  const form = new FormData();
  form.append("file", file);
  const params = new URLSearchParams({ domain, topic, source, language }).toString();
  const url = `/api/admin/ingest-document?${params}`;

  // XHR for real progress events
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.setRequestHeader("X-Admin-Key", getAdminKey());

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress({ stage: "Uploading", pct: Math.round((e.loaded / e.total) * 40) });
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          onProgress?.({ stage: "Complete", pct: 100 });
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject(new Error("Invalid response from server"));
        }
      } else {
        try {
          const err = JSON.parse(xhr.responseText);
          reject(new Error(err?.detail || `HTTP ${xhr.status}`));
        } catch {
          reject(new Error(`HTTP ${xhr.status}`));
        }
      }
    };
    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.send(form);
  });
}

// ─── Chunks ───────────────────────────────────────────────────────────────────
export const fetchChunks = (domain, page = 1, pageSize = 50) =>
  adminGet(`/api/admin/chunks?page=${page}&page_size=${pageSize}${domain ? "&domain=" + domain : ""}`);

// ─── Knowledge gaps ───────────────────────────────────────────────────────────
export const fetchKnowledgeGaps  = (status) => adminGet(`/api/admin/knowledge-gaps${status ? "?status=" + status : ""}`);
export const updateKnowledgeGap  = (id, status) => adminPatch(`/api/admin/knowledge-gaps/${id}`, { status });

// ─── Feedback ─────────────────────────────────────────────────────────────────
export const fetchFeedbackStats  = () => adminGet("/api/feedback/stats");
export const exportFeedbackUrl   = () => `/api/feedback/export?x_admin_key=${encodeURIComponent(getAdminKey())}`;

// ─── RAG management ───────────────────────────────────────────────────────────
export const fetchSnapshots = () => adminGet("/api/admin/snapshots");
export const rollbackIndex  = (steps) => adminPost(`/api/admin/rollback?steps=${steps}`, {});
