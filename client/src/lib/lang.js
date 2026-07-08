// Language preference (sent to the backend so the persona responds in
// the chosen language). Persisted to localStorage.

const KEY = "seelenruh:lang:v1";

export const LANGS = [
  { code: "auto", label: "Auto" },
  { code: "en", label: "English" },
  { code: "hi", label: "हिंदी / Hinglish" },
  { code: "de", label: "Deutsch" },
];

const listeners = new Set();

export function subscribeLang(cb) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function getLang() {
  try {
    return window.localStorage.getItem(KEY) || "hi";
  } catch {
    return "hi";
  }
}

export function setLang(code) {
  try {
    window.localStorage.setItem(KEY, code);
  } catch {
    // ignore
  }
  listeners.forEach((cb) => cb(code));
}
