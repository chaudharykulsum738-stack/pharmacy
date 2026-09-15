// Minimal service worker so the browser considers this a real, installable PWA.
// Caches the core static assets. Dynamic pages (dashboard data etc.) still
// need a live connection to the Flask server / MySQL - this only makes the
// app icon, manifest, and shell available offline.

const CACHE_NAME = "smart-pharmacy-v1";
const APP_SHELL = [
  "/static/manifest.json",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  // Cache-first for static assets, network for everything else (dashboard data must stay live)
  if (event.request.url.includes("/static/")) {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
  }
});
