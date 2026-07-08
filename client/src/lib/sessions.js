const STORAGE_KEY = "seelenruh:sessions:v1";
const TITLE_MAX = 60;

const DOMAINS = ["Mental Health", "Legal", "Government Schemes", "Safety"];

function emptyState() {
  return Object.fromEntries(DOMAINS.map((d) => [d, { sessions: [], activeId: null }]));
}

export function loadAll() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return emptyState();
    const parsed = JSON.parse(raw);
    const merged = emptyState();
    DOMAINS.forEach((d) => {
      if (parsed?.[d]?.sessions) {
        merged[d] = {
          sessions: parsed[d].sessions,
          activeId: parsed[d].activeId ?? null,
        };
      }
    });
    return merged;
  } catch {
    return emptyState();
  }
}

export function saveAll(state) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // ignore
  }
}

export function titleFromMessages(messages) {
  const firstUser = messages.find((m) => m.role === "user");
  if (!firstUser) return "New chat";
  const t = firstUser.content.replace(/\s+/g, " ").trim();
  return t.length > TITLE_MAX ? t.slice(0, TITLE_MAX - 1) + "…" : t;
}

export function newSession(messages = [], extras = {}) {
  return {
    id: crypto.randomUUID(),
    title: titleFromMessages(messages),
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages,
    isEmergency: false,
    ...extras,
  };
}
