// sw.js — Service Worker for AI TO AI HOLDING PWA
// Phase 19: Offline cache + background sync

const CACHE_NAME = 'aitai-v1';
const STATIC_ASSETS = [
  '/pwa',
  '/static/manifest.json',
  '/static/logo/logo-icon.svg',
  '/static/logo/favicon-32.png',
];

// Install: cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// Activate: cleanup old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch: network-first for API, cache-first for static
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // API calls: network only (don't cache sensitive data)
  if (url.pathname.startsWith('/v1/')) {
    event.respondWith(fetch(event.request));
    return;
  }

  // Static assets: cache-first
  event.respondWith(
    caches.match(event.request).then((cached) => {
      return cached || fetch(event.request).then((resp) => {
        // Cache new static assets
        if (resp.ok && resp.type === 'basic') {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return resp;
      });
    }).catch(() => {
      // Offline fallback
      if (event.request.mode === 'navigate') {
        return caches.match('/pwa');
      }
    })
  );
});

// Cache recent HS results in IndexedDB (for offline reference)
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'CACHE_HS_RESULT') {
    // Store in IndexedDB for offline lookup
    const result = event.data.payload;
    cacheHSResult(result);
  }
});

async function cacheHSResult(result) {
  try {
    const db = await openDB();
    const tx = db.transaction('hs_cache', 'readwrite');
    tx.objectStore('hs_cache').put({
      id: result.submission_id,
      data: result,
      cached_at: new Date().toISOString(),
    });
  } catch (e) {
    // IndexedDB not available — skip
  }
}

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('aitai_pwa', 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains('hs_cache')) {
        db.createObjectStore('hs_cache', { keyPath: 'id' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
