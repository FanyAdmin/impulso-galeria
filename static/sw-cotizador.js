// Service Worker del Cotizador Impulso
// Estrategia: red primero (para recibir precios actualizados) con respaldo en caché (offline)
const CACHE = 'cotizador-impulso-v1';
const PAGINA = '/cotizador-movil';

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.add(PAGINA)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (url.pathname === PAGINA) {
    e.respondWith(
      fetch(e.request).then(res => {
        const clon = res.clone();
        caches.open(CACHE).then(c => c.put(PAGINA, clon));
        return res;
      }).catch(() => caches.match(PAGINA))
    );
  }
});
