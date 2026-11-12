/**
 * Serve the production build locally, the way it will be hosted.
 *
 * This is the only way to exercise the service worker and the install
 * prompt: the development server does not register one. It also adds the
 * SPA fallback (any unknown path returns index.html) and keeps the shell and
 * the worker uncached so updates are picked up immediately.
 *
 * Usage (from the ``frontend`` directory):
 *
 *     npm run build
 *     node scripts/serve_build.js [port]
 */
'use strict';

const http = require('http');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', 'build');
const PORT = Number(process.argv[2] || process.env.PORT || 3000);
const HOST = process.env.HOST || '127.0.0.1';

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.webmanifest': 'application/manifest+json; charset=utf-8',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
  '.svg': 'image/svg+xml',
  '.txt': 'text/plain; charset=utf-8',
  '.woff2': 'font/woff2',
  '.map': 'application/json; charset=utf-8',
};

if (!fs.existsSync(ROOT)) {
  console.error('No build folder found. Run "npm run build" first.');
  process.exit(1);
}

function send(res, status, body, type, extraHeaders) {
  res.writeHead(status, Object.assign({ 'Content-Type': type }, extraHeaders || {}));
  res.end(body);
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const relative = decodeURIComponent(url.pathname).replace(/^\/+/, '');
  const filePath = path.resolve(ROOT, relative);

  // Never serve anything outside the build folder.
  if (!filePath.startsWith(ROOT)) {
    send(res, 403, 'Forbidden', 'text/plain; charset=utf-8');
    return;
  }

  const exists = fs.existsSync(filePath) && fs.statSync(filePath).isFile();
  const isShell = filePath === path.join(ROOT, 'index.html');
  const isWorker = filePath === path.join(ROOT, 'service-worker.js');

  if (!exists) {
    // SPA fallback.
    const index = fs.readFileSync(path.join(ROOT, 'index.html'));
    send(res, 200, index, TYPES['.html'], { 'Cache-Control': 'no-cache' });
    return;
  }

  const ext = path.extname(filePath).toLowerCase();
  const headers = {};
  if (isShell || isWorker) {
    headers['Cache-Control'] = 'no-cache';
  } else if (relative.startsWith('static/')) {
    headers['Cache-Control'] = 'public, max-age=31536000, immutable';
  }
  send(res, 200, fs.readFileSync(filePath), TYPES[ext] || 'application/octet-stream', headers);
});

server.listen(PORT, HOST, () => {
  console.log(`Serving ${ROOT} at http://${HOST}:${PORT}`);
});
