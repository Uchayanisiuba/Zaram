'use strict';

const { test } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { createStaticServer, isApiRequest } = require('../electron/staticServer');

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
