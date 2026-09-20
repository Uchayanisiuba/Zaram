'use strict';

const test = require('node:test');
const assert = require('node:assert');

const { releaseCard } = require('../electron/backend/releaseCard');

test('asks the backend to release the card with the launch credential', async () => {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, method: init.method, headers: init.headers });
    return { ok: true, status: 200 };
  };
  const out = await releaseCard('http://127.0.0.1:8420', { 'X-Zaram-Auth': 's' }, { fetchImpl });
  assert.deepStrictEqual(out, { released: true, status: 200 });
  assert.deepStrictEqual(calls, [
    { url: 'http://127.0.0.1:8420/providers/release', method: 'POST', headers: { 'X-Zaram-Auth': 's' } },
  ]);
});

test('a backend that does not answer does not keep the app open', async () => {
  // Never resolves until aborted — the shape of a hung backend.
  const fetchImpl = (_url, init) =>
    new Promise((_resolve, reject) => {
      init.signal.addEventListener('abort', () => reject(new Error('aborted')));
    });
  const started = Date.now();
  const out = await releaseCard('http://127.0.0.1:8420', {}, { fetchImpl, timeoutMs: 50 });
  assert.strictEqual(out.released, false);
  assert.ok(Date.now() - started < 2000);
});

test('a backend that is already gone is reported, not thrown', async () => {
  const fetchImpl = async () => { throw new Error('ECONNREFUSED'); };
  const out = await releaseCard('http://127.0.0.1:8420', {}, { fetchImpl });
  assert.deepStrictEqual(out, { released: false, error: 'ECONNREFUSED' });
});
