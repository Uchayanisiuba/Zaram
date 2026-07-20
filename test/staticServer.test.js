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
  const fetchImpl = async () => ({
    status: 200,
    headers: { forEach: () => {} },
    arrayBuffer: async () => new TextEncoder().encode('pong').buffer,
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
