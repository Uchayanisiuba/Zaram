'use strict';

const http = require('http');
const fs = require('fs');
const path = require('path');

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.woff2': 'font/woff2',
  '.ico': 'image/x-icon',
  '.webmanifest': 'application/manifest+json',
  '.map': 'application/json',
};

function isApiRequest(url, prefixes) {
  const p = url.split('?')[0];
  return prefixes.some((prefix) => p === prefix || p.startsWith(prefix + '/'));
}

function readBody(req) {
  if (req.method === 'GET' || req.method === 'HEAD') return Promise.resolve(undefined);
  return new Promise((resolve) => {
    const chunks = [];
    req.on('data', (c) => chunks.push(c));
    req.on('end', () => resolve(Buffer.concat(chunks)));
  });
}

async function proxy(req, res, baseUrl, fetchImpl) {
  const doFetch = fetchImpl || fetch;
  const target = baseUrl + req.url;
  const body = await readBody(req);
  const headers = {};
  for (const [k, v] of Object.entries(req.headers)) {
    if (k.toLowerCase() === 'host') continue;
    headers[k] = v;
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30000);
  try {
    const upstream = await doFetch(target, {
      method: req.method,
      headers,
      body,
      signal: controller.signal,
      redirect: 'manual',
    });
    res.statusCode = upstream.status;
    upstream.headers.forEach((v, k) => {
      const lk = k.toLowerCase();
      if (lk === 'transfer-encoding' || lk === 'connection') return;
      res.setHeader(k, v);
    });
    if (upstream.body) {
      upstream.body.pipe(res);
    } else {
      res.end();
    }
  } catch (err) {
    console.error('[StaticServer] Proxy error:', err);
    res.statusCode = 502;
    res.end('Backend unreachable');
  } finally {
    clearTimeout(timer);
  }
}

function serveFile(res, filePath) {
  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.statusCode = 404;
      res.end('Not found');
      return;
    }
    res.setHeader('Content-Type', MIME[path.extname(filePath)] || 'application/octet-stream');
    res.end(data);
  });
}

/**
 * Production static server for the built frontend.
 *
 * Serves `frontend/dist` and reverse-proxies API routes to the local backend.
 * Because the renderer and backend share one origin, no CORS configuration is
 * required and the backend stays hidden from arbitrary web origins.
 */
function createStaticServer({ staticDir, backendBaseUrl, apiPrefixes, fetchImpl }) {
  const server = http.createServer(async (req, res) => {
    try {
      if (isApiRequest(req.url, apiPrefixes)) {
        await proxy(req, res, backendBaseUrl, fetchImpl);
        return;
      }
      const urlPath = decodeURIComponent(req.url.split('?')[0]);
      const filePath = path.join(staticDir, urlPath === '/' ? 'index.html' : urlPath);
      if (!filePath.startsWith(staticDir)) {
        res.statusCode = 403;
        res.end('Forbidden');
        return;
      }
      if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
        serveFile(res, filePath);
        return;
      }
      const indexFile = path.join(staticDir, 'index.html');
      if (fs.existsSync(indexFile)) {
        serveFile(res, indexFile);
        return;
      }
      res.statusCode = 404;
      res.end('Frontend not built. Run the renderer build first.');
    } catch (_) {
      res.statusCode = 500;
      res.end('Server error');
    }
  });
  return server;
}

module.exports = { createStaticServer, isApiRequest };
