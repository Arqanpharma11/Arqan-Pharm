// Arqan PWA v36: network-first HTML, lightweight static shell, no bulk photo CacheStorage writes.
const CACHE_NAME = 'arkan-pharma-cloud-v36';
const SHELL = ['./index.html', './manifest.json', './arkan-logo.svg', './icons/arkan-192.png', './icons/arkan-512.png', './assets/arkan-platform-qr.svg'];
self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(SHELL)));
  self.skipWaiting();
});
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter(name => name.startsWith('arkan-pharma-cloud-') && name !== CACHE_NAME)
      .map(name => caches.delete(name)));
    await self.clients.claim();
  })());
});
self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  const isHtml = request.mode === 'navigate' || /\/index\.html$/.test(url.pathname);
  if (isHtml) {
    event.respondWith((async () => {
      try {
        const response = await fetch(new Request(request, { cache: 'no-store' }));
        if (response.ok) {
          const copy = response.clone();
          event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.put(request, copy)).catch(() => {}));
        }
        return response;
      } catch (_) {
        return await caches.match(request) || await caches.match('./index.html') || Response.error();
      }
    })());
    return;
  }
  // Let the browser's native HTTP cache handle product photos. Caching every
  // full-resolution pharmacy image into the service-worker cache caused
  // excessive writes and memory pressure when browsing large lists.
  if (url.pathname.includes('/assets/product-images/')) return;
  // Static icons and manifest remain available offline without caching catalog media.
  const staticNames = ['/manifest.json', '/arkan-logo.svg', '/icons/arkan-192.png', '/icons/arkan-512.png', '/assets/arkan-platform-qr.svg', '/assets/arkan-ui.css'];
  if (staticNames.some(name => url.pathname.endsWith(name))) {
    event.respondWith(caches.match(request).then(cached => cached || fetch(request)));
  }
});
