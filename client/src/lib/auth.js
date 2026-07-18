// Tiny auth state: token + user persisted in localStorage,
// a subscribe() / emit() pattern so the App can re-render on login/logout.

const TOKEN_KEY = "seelenruh:token:v1";
const REFRESH_KEY = "seelenruh:refresh:v1";
const USER_KEY = "seelenruh:user:v1";

// Per-user data kept in localStorage. Wiped when the user picks "also clear my
// data on this device" at logout. Preferences (theme, language) are intentionally
// excluded so they survive a sign-out on a shared device.
const USER_DATA_KEYS = [
  "seelenruh:sessions:v1",
  "seelenruh:saved:v1",
  "seelenruh:mood:v1",
  "seelenruh:active-domain:v1",
];

const listeners = new Set();

function emit() {
  listeners.forEach((cb) => cb());
}

export function subscribe(cb) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function getToken() {
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getRefreshToken() {
  try {
    return window.localStorage.getItem(REFRESH_KEY);
  } catch {
    return null;
  }
}

export function getUser() {
  try {
    const raw = window.localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setAuth({ token, refreshToken, user }) {
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
    if (refreshToken) window.localStorage.setItem(REFRESH_KEY, refreshToken);
    window.localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch {
    // ignore
  }
  emit();
}

export function clearAuth({ wipeUserData = false } = {}) {
  // tell the server to blacklist this token's jti — fire-and-forget
  const token = (() => {
    try {
      return window.localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  })();
  if (token) {
    try {
      fetch("/api/auth/logout", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        keepalive: true,
      }).catch(() => {});
    } catch {
      // ignore — local clear below is what actually signs the user out
    }
  }
  try {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(REFRESH_KEY);
    window.localStorage.removeItem(USER_KEY);
    if (wipeUserData) {
      USER_DATA_KEYS.forEach((k) => window.localStorage.removeItem(k));
    }
  } catch {
    // ignore
  }
  emit();
}

// exchanges refresh token for new token pair, returns true/false
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
  } catch {
    return false;
  }
}

export function isAuthed() {
  const token = getToken();
  if (!token) return false;
  try {
    // Decode payload (no signature verify — server validates on every request)
    const payload = JSON.parse(atob(token.split(".")[1]));
    if (payload.exp && Date.now() / 1000 > payload.exp) {
      // Token is expired — clear it so the app shows the login screen immediately
      // instead of waiting for a 401 response on the next API call.
      clearAuth();
      return false;
    }
  } catch {
    // Malformed token — treat as unauthenticated
    clearAuth();
    return false;
  }
  return true;
}

export async function signup({ email, name, password }) {
  // Signup no longer returns tokens — user must verify OTP first.
  return _postRaw("/api/auth/signup", { email, name, password });
}

export async function verifyOtp(email, otp) {
  // On success, server returns tokens — store them and emit.
  return _post("/api/auth/verify-otp", { email, otp });
}

export async function resendOtp(email) {
  return _postRaw("/api/auth/resend-otp", { email });
}

export async function login({ email, password }) {
  return _post("/api/auth/login", { email, password });
}

export async function deleteAccount() {
  const token = getToken();
  if (!token) throw new Error("You're not signed in.");
  let res;
  try {
    res = await fetch("/api/auth/me", {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new Error("Can't reach the backend. Is the Python server running on port 5000?");
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    // empty body is fine on success
  }
  if (!res.ok) {
    const msg = data?.detail || data?.error || `HTTP ${res.status}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data || { ok: true };
}

export async function forgotPassword(email) {
  return _postRaw("/api/auth/forgot-password", { email });
}

export async function resetPassword(token, newPassword) {
  return _postRaw("/api/auth/reset-password", { token, newPassword });
}

export async function verifyEmail(token) {
  return _postRaw("/api/auth/verify-email", { token });
}

export async function resendVerification() {
  const token = getToken();
  if (!token) throw new Error("You're not signed in.");
  let res;
  try {
    res = await fetch("/api/auth/resend-verification", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new Error("Can't reach the backend. Is the Python server running on port 5000?");
  }
  let data = null;
  try { data = await res.json(); } catch { /* empty body ok */ }
  if (!res.ok) {
    const msg = data?.detail || data?.error || `HTTP ${res.status}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data || { ok: true };
}

async function _postRaw(path, body) {
  let res;
  try {
    res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error("Can't reach the backend. Is the Python server running on port 5000?");
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    throw new Error(`Backend returned a non-JSON response (HTTP ${res.status}).`);
  }
  if (!res.ok) {
    const msg = data?.detail || data?.error || `HTTP ${res.status}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
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
    throw new Error("Can't reach the backend. Is the Python server running on port 5000?");
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    throw new Error(`Backend returned a non-JSON response (HTTP ${res.status}).`);
  }
  if (!res.ok) {
    const msg = data?.detail || data?.error || `HTTP ${res.status}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  setAuth({ token: data.token, refreshToken: data.refreshToken, user: data.user });
  return data;
}
