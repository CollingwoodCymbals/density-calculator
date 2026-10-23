// Offline cache for the Cymbal Density Calculator. Bump VERSION on every release.
const VERSION = "cc-density-1.1.0";
const FILES = [
  "./", "index.html", "manifest.webmanifest",
  "fonts/SourceSerif4-Semibold.woff2", "fonts/SourceSans3-Regular.woff2",
  "fonts/SourceSans3-Semibold.woff2", "fonts/SourceSans3-Bold.woff2",
  "icons/icon-192.png", "icons/icon-512.png", "icons/maskable-512.png",
  "icons/apple-touch-icon.png", "icons/logo-small.png"
];
self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
// Network first for the page so updates show straight away; cache first for everything else.
self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET" || new URL(req.url).origin !== location.origin) return;
  if (req.mode === "navigate") {
    // no-cache: always check GitHub for a newer page instead of using the browser's 10-minute copy
    e.respondWith(fetch(req, { cache: "no-cache" }).then(r => { const copy = r.clone(); caches.open(VERSION).then(c => c.put("index.html", copy)); return r; })
      .catch(() => caches.match("index.html")));
    return;
  }
  e.respondWith(caches.match(req).then(hit => hit || fetch(req)));
});
