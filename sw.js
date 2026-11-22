// Arqan PWA: keep HTML fresh while retaining an offline fallback.
const CACHE_NAME = 'arkan-pharma-cloud-v33';
const APP_SHELL = ['./index.html', './manifest.json', './arkan-logo.svg', './icons/arkan-192.png', './icons/arkan-512.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});
self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(key => key.startsWith('arkan-pharma-cloud-') && key !== CACHE_NAME).map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});
self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  const isDocument = request.mode === 'navigate' || url.pathname.endsWith('/index.html') || url.pathname.endsWith('/');
  if (isDocument) {
    // Never serve a stale HTML document while online.
    event.respondWith(fetch(new Request(request, { cache: 'no-store' })).then(response => {
      if (response.ok) { const copy = response.clone(); caches.open(CACHE_NAME).then(cache => cache.put(request, copy)).catch(() => {}); }
      return response;
    }).catch(async () => (await caches.match(request)) || (await caches.match('./index.html')) || Response.error()));
    return;
  }
  // Product photos are versioned/local and should remain available offline after first load.
  event.respondWith(fetch(request).then(response => {
    if (response.ok) caches.open(CACHE_NAME).then(cache => cache.put(request, response.clone())).catch(() => {});
    return response;
  }).catch(async () => (await caches.match(request)) || Response.error()));
});
