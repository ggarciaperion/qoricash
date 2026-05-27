/**
 * QoriCash Service Worker v1.0
 * Maneja push notifications en segundo plano y pantalla bloqueada.
 */

const CACHE_NAME = 'qoricash-v1';
const NOTIFICATION_SOUNDS = ['/static/sounds/allnotificaciones.mp3', '/static/sounds/completada.mp3'];

// ─── Instalación ─────────────────────────────────────────────────────────────
self.addEventListener('install', event => {
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(self.clients.claim());
});

// ─── Push Notifications ───────────────────────────────────────────────────────
self.addEventListener('push', event => {
    if (!event.data) return;

    let payload;
    try {
        payload = event.data.json();
    } catch (e) {
        payload = { title: 'QoriCash', body: event.data.text(), type: 'info' };
    }

    const iconMap = {
        success:  '/static/images/icon-success.png',
        warning:  '/static/images/icon-warning.png',
        danger:   '/static/images/icon-danger.png',
        info:     '/static/images/icon-info.png',
    };

    const options = {
        body:    payload.body || payload.message || '',
        icon:    iconMap[payload.type] || '/static/images/finalfinal.png',
        badge:   '/static/images/badge-72.png',
        tag:     payload.tag || 'qoricash-' + Date.now(),
        data:    { url: payload.url || '/', ...payload },
        vibrate: [200, 100, 200],
        requireInteraction: payload.priority === 'high',
        actions: payload.actions || [],
    };

    event.waitUntil(
        self.registration.showNotification(payload.title || 'QoriCash', options)
    );
});

// ─── Click en notificación ────────────────────────────────────────────────────
self.addEventListener('notificationclick', event => {
    event.notification.close();
    const url = event.notification.data?.url || '/';

    event.waitUntil(
        self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clients => {
            // Enfocar tab existente de QoriCash si hay una abierta
            for (const client of clients) {
                if (client.url.includes(self.location.origin) && 'focus' in client) {
                    client.focus();
                    client.navigate(url);
                    return;
                }
            }
            // Abrir nueva ventana
            if (self.clients.openWindow) {
                return self.clients.openWindow(url);
            }
        })
    );
});

// ─── Mensajes desde el cliente ────────────────────────────────────────────────
self.addEventListener('message', event => {
    if (event.data?.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});
