// Arqan PWA v39: conditional network-first HTML, lightweight static shell, no bulk photo CacheStorage writes.
const CACHE_NAME = 'arkan-pharma-cloud-v39';
const SHELL = ['./index.html', './manifest.json', './arkan-logo.svg', './icons/arkan-192.png', './icons/arkan-512.png', './assets/arkan-platform-qr.svg'];
self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => Promise.allSettled(SHELL.map(path => cache.add(new Request(path, {cache:'reload'}))))));
  self.skipWaiting();
});
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter(name => name.startsWith('arkan-pharma-cloud-') && name !== CACHE_NAME)
      .map(name => caches.delete(name)));
    if (self.registration.navigationPreload) { try { await self.registration.navigationPreload.enable(); } catch (_) {} }
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
        const preloaded = await event.preloadResponse;
        const response = preloaded || await fetch(new Request(request, { cache: 'no-cache' }));
        if (response.ok) {
          const copy = response.clone();
          event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.put(request, copy)).catch(() => {}));
        }
        return response;
      } catch (_) {
        const cached = await caches.match(request);
        const root = new URL('./', self.registration.scope);
        const main = url.pathname === root.pathname || url.pathname === root.pathname + 'index.html';
        return cached || (main ? await caches.match('./index.html') : null) || Response.error();
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
    event.respondWith((async () => {
      try { return await fetch(new Request(request, {cache:'no-cache'})); }
      catch (_) { return await caches.match(request) || Response.error(); }
    })());
  }
});
