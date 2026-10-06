/* Basira service worker — app shell only.
 * Never caches /v1/* or /health: verification results are always computed live (and never stored).
 * Strategy: navigation → network-first with cached shell fallback (offline page still opens);
 * hashed assets / fonts / brand → cache-first. Bump VERSION to invalidate. */
const VERSION = "basira-shell-v3"; // v3: purge caches that still held the pre-v4 favicon (E-064)
const SHELL = ["/", "/manifest.webmanifest", "/fonts/ReadexPro.woff2", "/brand/favicon/favicon.svg", "/brand/pwa/icon-192.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()),
  );
});
self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  if (url.pathname.startsWith("/v1/") || url.pathname === "/health" || url.pathname.startsWith("/docs") || url.pathname === "/openapi.json") return;
  if (req.mode === "navigate") {
    e.respondWith(
      fetch(req)
        .then((r) => {
          const copy = r.clone();
          caches.open(VERSION).then((c) => c.put("/", copy));
          return r;
        })
        .catch(() => caches.match("/").then((r) => r || Response.error())),
    );
    return;
  }
  if (/^\/(assets|fonts|brand)\//.test(url.pathname)) {
    e.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((r) => {
            if (r.ok) {
              const copy = r.clone();
              caches.open(VERSION).then((c) => c.put(req, copy));
            }
            return r;
          }),
      ),
    );
  }
});
