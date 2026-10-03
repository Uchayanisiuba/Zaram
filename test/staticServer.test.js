'use strict';

const { test } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { createStaticServer, isApiRequest } = require('../electron/staticServer');
const { createConfig } = require('../electron/config');

test('staticServer: isApiRequest matches prefixes', () => {
  const prefixes = ['/chat', '/api', '/personalities'];
  assert.strictEqual(isApiRequest('/chat', prefixes), true);
  assert.strictEqual(isApiRequest('/chat/stream', prefixes), true);
  assert.strictEqual(isApiRequest('/index.html', prefixes), false);
});

test('staticServer: serves built index and proxies API', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'zaram-static-'));
  fs.writeFileSync(path.join(dir, 'index.html'), '<html>app</html>');
  // The fake must return a *web* ReadableStream body, because that is what
  // `fetch` returns and what the proxy pipes. It used to return only
  // `arrayBuffer()`, from when the proxy buffered the whole response — so this
  // test failed the moment the proxy was changed to stream, and kept failing
  // unseen because nothing ran it.
  //
  // Streaming is not an optimisation here: `/chat` emits tokens as they are
  // generated, and buffering would hold the entire reply until the model
  // finished. A fake that cannot stream cannot test the thing that matters.
  const fetchImpl = async () => ({
    status: 200,
    headers: { forEach: () => {} },
    body: new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('pong'));
        controller.close();
      },
    }),
  });
  const server = createStaticServer({
    staticDir: dir,
    backendBaseUrl: 'http://127.0.0.1:9',
    apiPrefixes: ['/api', '/chat'],
    fetchImpl,
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const port = server.address().port;
  try {
    const res = await fetch(`http://127.0.0.1:${port}/`);
    assert.strictEqual(await res.text(), '<html>app</html>');

    const apiRes = await fetch(`http://127.0.0.1:${port}/chat`, { method: 'POST', body: '{}' });
    assert.strictEqual(await apiRes.text(), 'pong');
  } finally {
    await new Promise((r) => server.close(r));
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

/**
 * An unproxied API route is not an error. It is a document.
 *
 * This is the shape of the defect that made the egress log and the exporter
 * unreachable in every packaged build: a prefix absent from
 * `apiProxyPrefixes` falls through to the SPA handler and answers **200 with
 * index.html**, which the client then hands to `response.json()`. Nothing
 * anywhere reports a failure — not the server, not the proxy, not the log.
 *
 * Asserted here rather than only in the build guard because the guard checks
 * a list and this checks the consequence. A future refactor that makes the
 * fall-through 404 instead would be a real improvement, and this test would
 * be the thing that notices it happened.
 */
test('staticServer: a prefix nobody listed is answered with the app, not an error', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'zaram-static-'));
  fs.writeFileSync(path.join(dir, 'index.html'), '<!doctype html><html>app</html>');
  const server = createStaticServer({
    staticDir: dir,
    backendBaseUrl: 'http://127.0.0.1:9',
    apiPrefixes: ['/chat'],
    fetchImpl: async () => { throw new Error('should not be proxied'); },
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const port = server.address().port;
  try {
    const res = await fetch(`http://127.0.0.1:${port}/egress`);
    assert.strictEqual(res.status, 200, 'the trap is that it is not an error status');
    assert.match(res.headers.get('content-type'), /text\/html/);
    assert.match(await res.text(), /<!doctype html>/i);
  } finally {
    await new Promise((r) => server.close(r));
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

/**
 * The packaged origin forwards every prefix the dev origin does.
 *
 * `check-proxy-covers-backend.mjs` compares both lists against `main.py` at
 * build time and is the primary guard. This asserts the same agreement from
 * the suite, because the two lists live in different languages in different
 * directories owned by different halves of the project, and that is exactly
 * the arrangement that drifted for the entire life of the packaged build.
 */
test('staticServer: the packaged prefix list is not narrower than the dev one', () => {
  const packaged = new Set(createConfig({}).renderer.apiProxyPrefixes);
  const vite = fs.readFileSync(path.join(__dirname, '..', 'frontend', 'vite.config.js'), 'utf8');
  const dev = [...vite.slice(vite.indexOf('proxy:')).matchAll(/["'](\/[\w-]+)["']\s*:\s*\{/g)]
    .map(([, prefix]) => prefix);

  const missing = dev.filter((prefix) => !packaged.has(prefix));
  assert.deepStrictEqual(
    missing,
    [],
    `reachable in development and 200-with-a-document once packaged: ${missing.join(', ')}`,
  );
});

/**
 * Creating a project through the packaged origin: the exact call that failed.
 *
 * Reported 3 October 2026 against the installed alpha.3 — pick the repository
 * folder, press Create, nothing happens — with `projects.db` in the installed
 * data directory holding zero rows and untouched since the day it was made.
 *
 * In development the renderer talks to Vite's proxy; in a packaged build it
 * talks to this server. That difference is where a create can work on the
 * maintainer's machine and never once work on an install, so the packaged
 * path gets the POST exercised end to end rather than inferred from the
 * prefix list: the method, the JSON body, the credential header, and a JSON
 * reply coming back parseable.
 *
 * `res.json()` is the assertion that matters. An unlisted prefix answers 200
 * with index.html, and the store's `await res.json()` then throws on `<` —
 * which, before the fix in `projectStore.send`, rejected out of the store and
 * left the Create button disabled forever with nothing on screen.
 */
test('staticServer: POST /projects carries its body, its credential, and returns JSON', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'zaram-static-'));
  fs.writeFileSync(path.join(dir, 'index.html'), '<html>app</html>');

  let seen = null;
  const fetchImpl = async (url, init) => {
    seen = { url, method: init.method, headers: init.headers, body: init.body?.toString() };
    const payload = JSON.stringify({ id: 'ride-share', name: 'Ride Share', type: 'coding' });
    return {
      status: 200,
      headers: { forEach: () => {} },
      body: new ReadableStream({
        start(c) {
          c.enqueue(new TextEncoder().encode(payload));
          c.close();
        },
      }),
    };
  };

  // The real packaged prefix list, not a hand-written one. A test that
  // invents its own prefixes cannot notice `/projects` going missing from
  // the list the product actually ships.
  const { renderer } = createConfig({ isPackaged: true, env: {} });
  const apiProxyPrefixes = renderer.apiProxyPrefixes;
  const server = createStaticServer({
    staticDir: dir,
    backendBaseUrl: 'http://127.0.0.1:9',
    apiPrefixes: apiProxyPrefixes,
    fetchImpl,
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const port = server.address().port;
  try {
    const res = await fetch(`http://127.0.0.1:${port}/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Zaram-Auth': 'the-credential' },
      body: JSON.stringify({ name: 'Ride Share', type: 'coding', note: '', root: 'C:\RideShare' }),
    });

    // Parseable, which an index.html fall-through is not.
    const created = await res.json();
    assert.strictEqual(created.id, 'ride-share');

    assert.ok(seen, 'the request never reached the backend');
    assert.strictEqual(seen.method, 'POST');
    assert.strictEqual(seen.url, 'http://127.0.0.1:9/projects');
    // The folder has to survive the hop. A body dropped here is a project
    // created with no root, which is the "Zaram cannot see my code" report.
    assert.strictEqual(JSON.parse(seen.body).root, 'C:\RideShare');
    assert.strictEqual(seen.headers['x-zaram-auth'], 'the-credential');
  } finally {
    await new Promise((r) => server.close(r));
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
