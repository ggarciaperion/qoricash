/**
 * QoriCash Service Worker v3.0
 * Push notifications + PWA caching + offline support
 */

const CACHE_VERSION = 'v3.1';
const CACHE_STATIC  = `qoricash-static-${CACHE_VERSION}`;
const CACHE_PAGES   = `qoricash-pages-${CACHE_VERSION}`;
const OFFLINE_URL   = '/static/offline.html';

// Assets to pre-cache on install
const PRECACHE_ASSETS = [
  '/static/offline.html',
  '/static/manifest.json',
  '/static/images/pwa/icon-192x192.png',
  '/static/images/pwa/icon-512x512.png',
  '/static/images/pwa/apple-touch-icon.png',
  '/static/images/finalfinal.png',
  // Core CSS
  'https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css',
];

// Routes that should NEVER be cached (auth/operations/API)
const NEVER_CACHE = [
  '/api/',
  '/operations/api/',
  '/dashboard/api/',
  '/platform-api/',
  '/login',
  '/logout',
  '/auth/',
  '/register',
];

// Routes that are dynamic (network-first, short cache)
const NETWORK_FIRST = [
  '/dashboard',
  '/operations',
  '/clients',
  '/position',
];

// ─── Install ─────────────────────────────────────────────────────────────────
self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_STATIC).then(cache => {
      return Promise.allSettled(
        PRECACHE_ASSETS.map(url => cache.add(url).catch(() => {}))
      );
    })
  );
});

// ─── Activate — cleanup old caches ───────────────────────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(k => k.startsWith('qoricash-') && k !== CACHE_STATIC && k !== CACHE_PAGES)
          .map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ─── Fetch — caching strategies ──────────────────────────────────────────────
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Only handle same-origin + CDN requests
  if (request.method !== 'GET') return;
  if (!['https:', 'http:'].includes(url.protocol)) return;

  // 1. NEVER CACHE — API calls, auth, sensitive routes
  if (NEVER_CACHE.some(p => url.pathname.startsWith(p))) return;

  // 2. Static assets — Cache First (fast load)
  if (isStaticAsset(url)) {
    event.respondWith(cacheFirst(request, CACHE_STATIC));
    return;
  }

  // 3. Navigation/pages — Network First with offline fallback
  if (request.mode === 'navigate') {
    event.respondWith(networkFirstWithOffline(request));
    return;
  }
});

function isStaticAsset(url) {
  const ext = url.pathname.split('.').pop();
  const staticExts = ['css','js','png','jpg','jpeg','gif','svg','ico','woff','woff2','ttf','mp3','mp4'];
  if (staticExts.includes(ext)) return true;
  if (url.pathname.startsWith('/static/')) return true;
  if (url.hostname.includes('cdn.jsdelivr.net')) return true;
  if (url.hostname.includes('cdnjs.cloudflare.com')) return true;
  return false;
}

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('', { status: 408 });
  }
}

async function networkFirstWithOffline(request) {
  const cache = await caches.open(CACHE_PAGES);
  try {
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await cache.match(request);
    if (cached) return cached;
    const offline = await caches.match(OFFLINE_URL);
    return offline || new Response('Sin conexión', { status: 503 });
  }
}

// ─── Push Notifications ───────────────────────────────────────────────────────
self.addEventListener('push', event => {
  if (!event.data) return;

  let payload;
  try { payload = event.data.json(); }
  catch (e) { payload = { title: 'QoriCash', body: event.data.text(), type: 'info' }; }

  const iconMap = {
    success: '/static/images/pwa/icon-192x192.png',
    warning: '/static/images/pwa/icon-192x192.png',
    danger:  '/static/images/pwa/icon-192x192.png',
    info:    '/static/images/pwa/icon-192x192.png',
  };

  const options = {
    body:    payload.body || payload.message || '',
    icon:    iconMap[payload.type] || '/static/images/pwa/icon-192x192.png',
    badge:   '/static/images/pwa/badge-72.png',
    tag:     payload.tag || 'qoricash-' + Date.now(),
    data:    { url: payload.url || '/dashboard', ...payload },
    vibrate: [200, 100, 200],
    requireInteraction: payload.priority === 'high',
    actions: payload.actions || [],
  };

  event.waitUntil(
    self.registration.showNotification(payload.title || 'QoriCash', options)
  );
});

// ─── Notification click ───────────────────────────────────────────────────────
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = event.notification.data?.url || '/dashboard';

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clients => {
      for (const client of clients) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.focus();
          client.navigate(url);
          return;
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});

// ─── Message from client ──────────────────────────────────────────────────────
self.addEventListener('message', event => {
  if (event.data?.type === 'SKIP_WAITING') self.skipWaiting();
  if (event.data?.type === 'CLEAR_CACHE') {
    caches.keys().then(keys => keys.forEach(k => caches.delete(k)));
  }
});
