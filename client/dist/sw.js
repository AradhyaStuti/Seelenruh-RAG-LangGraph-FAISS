/**
 * Seelenruh Service Worker
 *
 * Strategy:
 *   - App shell (JS/CSS/HTML): Cache-first with background revalidation (stale-while-revalidate)
 *   - API calls:               Network-first with offline fallback message
 *   - Static assets:           Cache-first (content-hashed filenames never change)
 *   - Fonts:                   Cache-first (long TTL)
 *
 * Offline UX:
 *   - If the user is offline and requests the app, serve the cached shell.
 *   - API chat requests fail gracefully (no service worker intercept — the app
 *     handles the error via its own offline fallback UI).
 */

const CACHE_NAME = "seelenruh-v1";
const SHELL_URLS = ["/", "/index.html"];

// ── Install: pre-cache the app shell ─────────────────────────────────────────
self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_URLS))
  );
});

// ── Activate: remove stale caches ────────────────────────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k !== CACHE_NAME)
            .map((k) => caches.delete(k))
        )
      )
      .then(() => self.clients.claim())
  );
});

// ── Fetch: routing strategy ───────────────────────────────────────────────────
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Never intercept API calls — let them fail naturally so app error handling works
  if (url.pathname.startsWith("/api/")) return;

  // Skip non-GET requests
  if (event.request.method !== "GET") return;

  // Skip cross-origin requests (fonts fetched directly from fonts.googleapis.com)
  if (url.origin !== self.location.origin) return;

  // Hashed assets (contain a hash in the filename) — cache-first forever
  if (url.pathname.startsWith("/assets/")) {
    event.respondWith(
      caches.match(event.request).then(
        (cached) =>
          cached ||
          fetch(event.request).then((response) => {
            if (response && response.status === 200) {
              const clone = response.clone();
              caches.open(CACHE_NAME).then((c) => c.put(event.request, clone));
            }
            return response;
          })
      )
    );
    return;
  }

  // App shell — stale-while-revalidate
  event.respondWith(
    caches.open(CACHE_NAME).then((cache) =>
      cache.match(event.request).then((cached) => {
        const networkFetch = fetch(event.request)
          .then((response) => {
            if (response && response.status === 200) {
              cache.put(event.request, response.clone());
            }
            return response;
          })
          .catch(() => cached); // offline: return cached version

        // Return cached immediately; update in background
        return cached || networkFetch;
      })
    )
  );
});
