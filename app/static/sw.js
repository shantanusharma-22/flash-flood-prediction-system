// Service Worker for NDRF Disaster Early Warning PWA
// Cache strategy: network-first for the app shell only.
// Telemetry endpoints (/api/*, /ws/*) are NEVER cached — warning data must be live,
// and SOS/dispatch payloads must not linger in a shared browser cache.
const CACHE_NAME = 'ndrf-shell-v2';
const SHELL_ASSETS = [
  '/',
  '/manifest.json',
  '/static/app.js',
  '/static/tailwind-config.js'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // Same-origin only: let CDN scripts, fonts and map tiles go straight to network.
  if (url.origin !== self.location.origin) return;

  // Live data paths are never cached.
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/ws/')) return;

  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response && response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        }
        return response;
      })
      .catch(() => caches.match(request))
  );
});
