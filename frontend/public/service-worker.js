/* ClauseGuard offline shell.
 *
 * What this caches:
 *   - the app shell (index.html), the offline page, the manifest and icons
 *   - hashed build assets under /static (JavaScript, CSS, fonts)
 *
 * What this NEVER caches:
 *   - anything from the API (contracts, analyses, chats, reminders, accounts)
 *   - any request that carries an Authorization header
 *   - anything on another origin
 *
 * The rules below are deliberately conservative: if a request is not clearly
 * a static asset of this site, it goes straight to the network and is never
 * written to a cache. Your contracts are never stored on the device by the
 * service worker.
 */
const VERSION = 'v4';
const SHELL_CACHE = `clauseguard-shell-${VERSION}`;
const STATIC_CACHE = `clauseguard-static-${VERSION}`;
const CACHE_PREFIX = 'clauseguard-';
const OFFLINE_URL = '/offline.html';
const SHELL_URL = '/index.html';

const SHELL_ASSETS = [
  '/',
  SHELL_URL,
  OFFLINE_URL,
  '/manifest.json',
  '/favicon.ico',
  '/logo192.png',
  '/logo512.png',
  '/apple-touch-icon.png',
];

/* API paths live next to the app when the backend is served from the same
 * origin. They are excluded from every cache rule. */
const API_PREFIXES = [
  '/api',
  '/auth',
  '/analyze',
  '/upload',
  '/chat',
  '/compare',
  '/drift',
  '/contracts',
  '/reminders',
  '/checklist',
  '/bookmarks',
  '/dates',
  '/stats',
  '/history',
  '/fair-clauses',
  '/health',
  '/terms-checker',
  '/settings',
  '/openapi.json',
  '/docs',
  '/redoc',
];

function isApiPath(pathname) {
  const path = pathname.toLowerCase();
  return API_PREFIXES.some((prefix) => path === prefix || path.startsWith(prefix + '/') || path.startsWith(prefix + '?'));
}

function isStaticAsset(pathname) {
  return (
    pathname.startsWith('/static/') ||
    /\.(?:js|css|woff2?|ttf|otf|png|jpe?g|svg|webp|ico|json)$/i.test(pathname)
  );
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL_CACHE);
      // Each asset is added individually: one missing file must not break the
      // whole install.
      await Promise.all(
        SHELL_ASSETS.map((url) =>
          cache.add(new Request(url, { cache: 'reload' })).catch(() => undefined)
        )
      );
      // No skipWaiting() here: a new version waits until the user chooses to
      // refresh, so nobody loses their place mid-read.
    })()
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      const stale = keys.filter(
        (key) => key.startsWith(CACHE_PREFIX) && !key.endsWith(VERSION)
      );

      // Carry the build files over before dropping the old caches, so a page
      // that was open during the update keeps working if the connection drops.
      if (stale.length > 0) {
        const target = await caches.open(STATIC_CACHE);
        for (const oldKey of stale) {
          if (!oldKey.startsWith('clauseguard-static-')) continue;
          const oldCache = await caches.open(oldKey);
          const requests = await oldCache.keys();
          for (const request of requests) {
            const response = await oldCache.match(request);
            if (response) {
              try {
                await target.put(request, response);
              } catch (err) {
                /* a single unreadable file must not block the update */
              }
            }
          }
        }
      }

      await Promise.all(stale.map((key) => caches.delete(key)));

      // Drop build files that the current release no longer uses, so the
      // cache does not grow with every update.
      try {
        const manifest = await fetch('/asset-manifest.json', { cache: 'no-cache' }).then((r) =>
          r.ok ? r.json() : null
        );
        if (manifest && manifest.files) {
          const keep = new Set(
            Object.values(manifest.files).map((file) => new URL(file, self.location.origin).pathname)
          );
          const cache = await caches.open(STATIC_CACHE);
          const requests = await cache.keys();
          await Promise.all(
            requests
              .filter((r) => !keep.has(new URL(r.url).pathname))
              .map((r) => cache.delete(r))
          );
        }
      } catch (err) {
        // Offline during activation: keep what we have.
      }
      await self.clients.claim();
    })()
  );
});

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

async function handleNavigation(request) {
  const cache = await caches.open(SHELL_CACHE);
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      if (response.type === 'basic') {
        // The SPA shell is the same document for every route.
        await cache.put(SHELL_URL, response.clone());
      }
      return response;
    }
    // A server or proxy error (502/503) is not a usable page: fall through to
    // the cached shell instead of showing a raw error document.
  } catch (err) {
    // No connection at all — same fallback below.
  }
  const shell = await cache.match(SHELL_URL);
  if (shell) return shell;
  const offline = await cache.match(OFFLINE_URL);
  if (offline) return offline;
  return new Response('ClauseGuard is offline right now.', {
    status: 503,
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
}

async function handleStatic(request) {
  const cache = await caches.open(STATIC_CACHE);
  const cached = await cache.match(request);
  const network = fetch(request)
    .then((response) => {
      if (response && response.ok && response.type === 'basic') {
        cache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => undefined);
  if (cached) {
    return cached;
  }
  const response = await network;
  return (
    response ||
    new Response('', { status: 504, headers: { 'Content-Type': 'text/plain; charset=utf-8' } })
  );
}

self.addEventListener('fetch', (event) => {
  const request = event.request;

  if (request.method !== 'GET') return;

  let url;
  try {
    url = new URL(request.url);
  } catch (err) {
    return;
  }

  // Other origins (the API host, fonts hosted elsewhere) are left alone.
  if (url.origin !== self.location.origin) return;

  // Never touch authenticated traffic.
  if (request.headers.has('authorization')) return;

  // Page loads: network first, then the cached shell, then the offline page.
  if (request.mode === 'navigate') {
    event.respondWith(handleNavigation(request));
    return;
  }

  // Everything that could be private stays out of the caches.
  if (isApiPath(url.pathname)) return;

  if (isStaticAsset(url.pathname)) {
    event.respondWith(handleStatic(request));
  }
});
