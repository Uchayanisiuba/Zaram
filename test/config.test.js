'use strict';

const { test } = require('node:test');
const assert = require('node:assert');
const { createConfig } = require('../electron/config');

test('createConfig: dev mode points renderer at the Vite dev server', () => {
  const cfg = createConfig({ isDev: true, appPath: 'C:\\app', userDataPath: 'C:\\data' });
  assert.strictEqual(cfg.isDev, true);
  assert.strictEqual(cfg.renderer.url, 'http://localhost:5173');
  assert.ok(cfg.renderer.devUrl.includes('5173'));
});

test('createConfig: prod mode points renderer at the local static server', () => {
  const cfg = createConfig({ isDev: false, appPath: 'C:\\app', userDataPath: 'C:\\data' });
  assert.strictEqual(cfg.isDev, false);
  assert.strictEqual(cfg.renderer.url, 'http://127.0.0.1:5180');
  assert.strictEqual(cfg.backend.baseUrl, 'http://127.0.0.1:8000');
});

test('createConfig: derives platform-aware paths from userData', () => {
  const cfg = createConfig({ isDev: false, appPath: '/app', userDataPath: '/data' });
  const norm = cfg.settingsPath.replace(/\\/g, '/');
  assert.ok(norm.endsWith('/data/settings.json'));
  assert.ok(cfg.windowStatePath.replace(/\\/g, '/').endsWith('/data/window-state.json'));
  assert.ok(cfg.logsPath.replace(/\\/g, '/').endsWith('/data/logs'));
});

test('createConfig: window enforces minimum size', () => {
  const cfg = createConfig({ isDev: false, appPath: '/app', userDataPath: '/data' });
  assert.ok(cfg.window.minWidth >= 800);
  assert.ok(cfg.window.minHeight >= 600);
});
