const CACHE_NAME = 'arkan-pharma-cloud-v23';
const ASSETS_TO_CACHE = ['./','./index.html','./manifest.json','./arkan-logo.svg','./icons/arkan-192.png','./icons/arkan-512.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS_TO_CACHE)));
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
  if (event.request.method !== 'GET') return;
  event.respondWith(fetch(event.request).then(response => {
    if (response && response.status === 200 && new URL(event.request.url).origin === self.location.origin) {
      const clone = response.clone();
      caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone)).catch(() => {});
    }
    return response;
  }).catch(() => caches.match(event.request)));
});
