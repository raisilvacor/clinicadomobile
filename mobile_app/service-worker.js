// Service Worker para PWA
const CACHE_NAME = 'clinica-cel-v1';
const urlsToCache = [
  '/mobile_app/',
  '/mobile_app/index.html',
  '/mobile_app/manifest.json',
  '/mobile_app/icon-192.png',
  '/mobile_app/icon-512.png'
];

// Instalar Service Worker
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(urlsToCache))
  );
});

// Ativar Service Worker
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// Interceptar requisições
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // Retornar do cache ou buscar da rede
        return response || fetch(event.request);
      })
  );
});

// Notificações push (será implementado depois)
self.addEventListener('push', (event) => {
  const options = {
    body: event.data ? event.data.text() : 'Nova notificação',
    icon: '/mobile_app/icon-192.png',
    badge: '/mobile_app/icon-192.png',
    vibrate: [200, 100, 200],
    tag: 'repair-notification'
  };
  
  event.waitUntil(
    self.registration.showNotification('Clínica CEL', options)
  );
});
