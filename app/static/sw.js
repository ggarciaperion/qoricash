/**
 * QoriCash Service Worker v3.2
 * Push notifications + PWA caching + offline support
 *
 * Caching strategy:
 *  - CSS/HTML: NEVER cached by SW (browser HTTP cache handles it — avoids stale layout)
 *  - Images/fonts/audio: Cache-First (immutable assets)
 *  - JS: Cache-First only for versioned static JS
 *  - Navigation: Network-First with offline fallback
 *  - API/auth: Never cached
 */

const CACHE_VERSION = 'v3.2';
const CACHE_STATIC  = `qoricash-static-${CACHE_VERSION}`;
const CACHE_PAGES   = `qoricash-pages-${CACHE_VERSION}`;
const OFFLINE_URL   = '/offline';

// Pre-cache only immutable binary assets (no CSS — avoids desktop layout regression)
const PRECACHE_ASSETS = [
  '/static/images/pwa/icon-192x192.png',
  '/static/images/pwa/icon-512x512.png',
  '/static/images/pwa/apple-touch-icon.png',
  '/static/images/finalfinal.png',
];

// Routes that must NEVER be cached (auth, operations, API)
const NEVER_CACHE = [
  '/api/',
  '/operations/api/',
  '/dashboard/api/',
  '/platform-api/',
  '/datatec/',
  '/login',
  '/logout',
  '/auth/',
  '/register',
];

// ─── Install ─────────────────────────────────────────────────────────────────
self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_STATIC).then(cache =>
      Promise.allSettled(
        PRECACHE_ASSETS.map(url => cache.add(url).catch(() => {}))
      )
    )
  );
});

// ─── Activate — flush all previous caches ────────────────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys =>
        Promise.all(
          keys
            .filter(k => k.startsWith('qoricash-') && k !== CACHE_STATIC && k !== CACHE_PAGES)
            .map(k => caches.delete(k))
        )
      )
      .then(() => self.clients.claim())
  );
});

// ─── Fetch — caching strategies ──────────────────────────────────────────────
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Only handle HTTP(S) GET requests
  if (request.method !== 'GET') return;
  if (!['https:', 'http:'].includes(url.protocol)) return;

  // 1. NEVER CACHE — API calls, auth, sensitive routes
  if (NEVER_CACHE.some(p => url.pathname.startsWith(p))) return;

  // 2. CSS files — always network (never SW-cache; avoids stale desktop layout)
  if (url.pathname.endsWith('.css') || url.pathname.includes('.css?')) return;

  // 3. Layout-critical HTML — never cache (always fresh from server)
  if (url.pathname === '/' || url.pathname === '/login' || url.pathname === '/dashboard') return;

  // 4. Immutable binary assets — Cache First
  if (isImmutableAsset(url)) {
    event.respondWith(cacheFirst(request, CACHE_STATIC));
    return;
  }

  // 5. Navigation — Network First with offline fallback
  if (request.mode === 'navigate') {
    event.respondWith(networkFirstWithOffline(request));
    return;
  }
});

/**
 * Cache-first only for truly immutable assets: images, fonts, audio, icons.
 * CSS and JS that affect layout are NOT cached here.
 */
function isImmutableAsset(url) {
  const p = url.pathname;
  // Images / fonts / audio
  if (/\.(png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot|mp3|mp4|webp)(\?|$)/.test(p)) return true;
  // PWA-specific static paths (only binary assets)
  if (p.startsWith('/static/images/')) return true;
  if (p.startsWith('/static/sounds/')) return true;
  // Apple touch icon served from root
  if (p === '/apple-touch-icon.png' || p === '/apple-touch-icon-precomposed.png') return true;
  return false;
}

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok && response.status !== 0) {
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
    // Serve offline page
    const offlinePage = await caches.match(OFFLINE_URL);
    if (offlinePage) return offlinePage;
    // Try to fetch offline page fresh
    try {
      return await fetch(OFFLINE_URL);
    } catch {
      return new Response('<html><body><h2>Sin conexión</h2></body></html>', {
        status: 503,
        headers: { 'Content-Type': 'text/html' },
      });
    }
  }
}

// ─── Push Notifications ───────────────────────────────────────────────────────
self.addEventListener('push', event => {
  if (!event.data) return;

  let payload;
  try { payload = event.data.json(); }
  catch (e) { payload = { title: 'QoriCash', body: event.data.text(), type: 'info' }; }

  const options = {
    body:    payload.body || payload.message || '',
    icon:    '/static/images/pwa/icon-192x192.png',
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
