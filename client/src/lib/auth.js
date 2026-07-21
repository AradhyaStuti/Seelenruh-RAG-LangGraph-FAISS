// Auth state: token + user in localStorage.
// subscribe() / emit() lets the App re-render on login/logout.

const TOKEN_KEY = "seelenruh:token:v1";
const REFRESH_KEY = "seelenruh:refresh:v1";
const USER_KEY = "seelenruh:user:v1";

const USER_DATA_KEYS = [
  "seelenruh:sessions:v1",
  "seelenruh:saved:v1",
  "seelenruh:mood:v1",
  "seelenruh:active-domain:v1",
];

const listeners = new Set();
function emit() { listeners.forEach((cb) => cb()); }

export function subscribe(cb) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function getToken() {
  try { return window.localStorage.getItem(TOKEN_KEY); } catch { return null; }
}

export function getRefreshToken() {
  try { return window.localStorage.getItem(REFRESH_KEY); } catch { return null; }
}

export function getUser() {
  try {
    const raw = window.localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

export function setAuth({ token, refreshToken, user }) {
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
    if (refreshToken) window.localStorage.setItem(REFRESH_KEY, refreshToken);
    window.localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch { /* ignore */ }
  emit();
}

export function clearAuth({ wipeUserData = false } = {}) {
  const token = (() => { try { return window.localStorage.getItem(TOKEN_KEY); } catch { return null; } })();
  if (token) {
    try {
      fetch("/api/auth/logout", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        keepalive: true,
      }).catch(() => {});
    } catch { /* ignore */ }
  }
  try {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(REFRESH_KEY);
    window.localStorage.removeItem(USER_KEY);
    if (wipeUserData) USER_DATA_KEYS.forEach((k) => window.localStorage.removeItem(k));
  } catch { /* ignore */ }
  emit();
}

export async function silentRefresh() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;
  try {
    const res = await fetch("/api/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    if (!data?.token) return false;
    setAuth({ token: data.token, refreshToken: data.refreshToken, user: data.user });
    return true;
  } catch { return false; }
}

export function isAuthed() {
  const token = getToken();
  if (!token) return false;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    if (payload.exp && Date.now() / 1000 > payload.exp) { clearAuth(); return false; }
  } catch { clearAuth(); return false; }
  return true;
}

export async function signup({ email, name, password }) {
  return _post("/api/auth/signup", { email, name, password });
}

export async function login({ email, password }) {
  return _post("/api/auth/login", { email, password });
}

export async function deleteAccount() {
  const token = getToken();
  if (!token) throw new Error("You're not signed in.");
  const res = await fetch("/api/auth/me", {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
  return data || { ok: true };
}

async function _post(path, body) {
  let res;
  try {
    res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error("Can't reach the server. Please check your connection.");
  }
  let data = null;
  try { data = await res.json(); } catch {
    throw new Error(`Something went wrong (HTTP ${res.status}). Please try again.`);
  }
  if (!res.ok) {
    const msg = data?.detail || data?.error || `HTTP ${res.status}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  setAuth({ token: data.token, refreshToken: data.refreshToken, user: data.user });
  return data;
}
