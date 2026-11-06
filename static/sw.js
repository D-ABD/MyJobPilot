const CACHE_NAME = "myjobpilot-shell-v3";
const SHELL_ASSETS = [
  "/",
  "/offline/",
  "/static/css/custom.css",
  "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
  "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
];
const PRIVATE_PREFIXES = ["/dashboard/", "/staff/", "/admin-dashboard/", "/documents/", "/entreprises/", "/mon-compte/"];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(SHELL_ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET") return;
  if (url.origin !== self.location.origin) {
    if (SHELL_ASSETS.includes(request.url)) {
      event.respondWith(caches.match(request).then(cached => cached || fetch(request)));
    }
    return;
  }
  if (PRIVATE_PREFIXES.some(prefix => url.pathname.startsWith(prefix))) return;
  if (url.pathname.startsWith("/static/")) {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_NAME);
      const cached = await cache.match(request);
      if (cached) return cached;

      const response = await fetch(request);
      if (response.ok) {
        const responseToCache = response.clone();
        try {
          await cache.put(request, responseToCache);
        } catch (error) {
          // Le chargement reste disponible même si l'écriture du cache échoue.
        }
      }
      return response;
    })());
    return;
  }
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match("/offline/")));
  }
});
