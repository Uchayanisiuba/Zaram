'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const Module = require('node:module');
const { EventEmitter } = require('node:events');

test('the shipping browser attaches through WindowManager.getMainWindow', () => {
  const fs = require('node:fs');
  const main = fs.readFileSync(require('node:path').join(__dirname, '../electron/main.js'), 'utf8');
  const construction = main.slice(main.indexOf('browser = createBrowserService({'), main.indexOf('ambient = createAmbientSurface({'));
  assert.match(construction, /getWindow: \(\) => windows && windows\.getMainWindow\(\)/);
  assert.doesNotMatch(construction, /windows\.getMain\(/);
});

function fixture(load = async () => {}) {
  const contents = [];
  class View {
    constructor() {
      const wc = new EventEmitter();
      Object.assign(wc, { loadURL: load, setWindowOpenHandler() {}, canGoBack: () => false,
        canGoForward: () => false, isLoading: () => false, close() {} });
      this.webContents = wc;
      contents.push(wc);
    }
    setBounds() {}
  }
  const original = Module._load;
  Module._load = function(name, ...args) {
    if (name === 'electron') return { BrowserView: View, session: {
      fromPartition: () => ({ webRequest: { onBeforeSendHeaders() {} } })
    } };
    return original.call(this, name, ...args);
  };
  const path = require.resolve('../electron/services/browserService');
  delete require.cache[path];
  let createBrowserService;
  try { ({ createBrowserService } = require(path)); } finally { Module._load = original; }
  let event;
  const service = createBrowserService({ getWindow: () => ({ addBrowserView() {}, removeBrowserView() {} }),
    reportEgress() {}, isBrowseAllowed: () => false, emit: (value) => { event = value; } });
  const id = service.create();
  return { service, id, contents, event: () => event };
}

test('navigation success waits for the page load', async () => {
  let resolve;
  const f = fixture(() => new Promise((done) => { resolve = done; }));
  let settled = false;
  const pending = f.service.navigate(f.id, 'http://localhost:3000').then((result) => {
    settled = true; return result;
  });
  await Promise.resolve();
  assert.equal(settled, false);
  resolve();
  assert.equal((await pending).loaded, true);
});

test('a failed page is reported and can recover', async () => {
  let fail = true;
  const f = fixture(async () => { if (fail) throw new Error('ERR_CONNECTION_REFUSED'); });
  const result = await f.service.navigate(f.id, 'http://localhost:3000');
  assert.equal(result.loaded, false);
  assert.match(f.event().tabs[0].error, /ERR_CONNECTION_REFUSED/);
  fail = false;
  assert.equal((await f.service.navigate(f.id, 'http://localhost:3000')).loaded, true);
  assert.equal(f.event().tabs[0].error, '');
});

test('unsafe and nonconsented navigation never loads', async () => {
  let calls = 0;
  const f = fixture(async () => { calls++; });
  assert.equal((await f.service.navigate(f.id, 'javascript:alert(1)')).allow, false);
  assert.equal((await f.service.navigate(f.id, 'https://example.com')).allow, false);
  assert.equal(calls, 0);
});

test('main frame failures and crashes are observable', () => {
  const f = fixture();
  f.contents[0].emit('did-fail-load', {}, -102, 'ERR_CONNECTION_REFUSED', 'http://localhost:3000', true);
  assert.match(f.event().tabs[0].error, /ERR_CONNECTION_REFUSED/);
  f.contents[0].emit('render-process-gone', {}, { reason: 'crashed' });
  assert.match(f.event().tabs[0].error, /crashed/);
});
