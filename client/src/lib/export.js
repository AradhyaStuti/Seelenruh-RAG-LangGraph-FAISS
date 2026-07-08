// Bundle everything the user has stored locally (chat sessions per persona,
// mood trail, saved messages) into one JSON file and trigger a download.

import { getUser } from "@/lib/auth";

const SESSIONS_KEY = "seelenruh:sessions:v1";
const SAVED_KEY = "seelenruh:saved:v1";
const MOOD_KEY = "seelenruh:mood:v1";

function readJSON(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

export function buildExport() {
  const user = getUser();
  return {
    app: "Seelenruh",
    schemaVersion: 1,
    exportedAt: new Date().toISOString(),
    user: user ? { email: user.email, name: user.name } : null,
    sessions: readJSON(SESSIONS_KEY, {}),
    savedMoments: readJSON(SAVED_KEY, []),
    moodTrail: readJSON(MOOD_KEY, []),
  };
}

export function downloadExport() {
  const payload = buildExport();
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const stamp = new Date().toISOString().slice(0, 10);
  const a = document.createElement("a");
  a.href = url;
  a.download = `seelenruh-export-${stamp}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return payload;
}
