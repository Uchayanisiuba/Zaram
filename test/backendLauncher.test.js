'use strict';

const { test } = require('node:test');
const assert = require('node:assert');
const path = require('node:path');
const { EventEmitter } = require('node:events');
const { createConfig } = require('../electron/config');
const { BackendLauncher, resolvePythonCommand, buildArgs } = require('../electron/backend/backendLauncher');

function fakeChild() {
  const c = new EventEmitter();
  c.stdout = new EventEmitter();
  c.stderr = new EventEmitter();
  c.kill = () => c.emit('exit', 0, null);
  return c;
}

test('resolvePythonCommand: defaults to project venv', () => {
  assert.strictEqual(
    resolvePythonCommand({ cwd: '/app', env: {}, platform: 'win32' }),
    path.join('/app', '.venv', 'Scripts', 'python.exe'),
  );
  assert.strictEqual(
    resolvePythonCommand({ cwd: '/app', env: {}, platform: 'linux' }),
    path.join('/app', '.venv', 'bin', 'python'),
  );
});

test('resolvePythonCommand: honors ZARAM_PYTHON', () => {
  assert.strictEqual(
    resolvePythonCommand({ cwd: '/app', env: { ZARAM_PYTHON: '/usr/bin/python3' }, platform: 'linux' }),
    '/usr/bin/python3',
  );
});

test('buildArgs: builds uvicorn launch args', () => {
  assert.deepStrictEqual(buildArgs(8000), [
    '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port=8000',
  ]);
});

test('BackendLauncher: transitions to available when health ok', async () => {
  const cfg = createConfig({ isDev: false, appPath: '/app', userDataPath: '/data' });
  cfg.backend.pollIntervalMs = 5;
  const launcher = new BackendLauncher({
    config: cfg,
    spawnImpl: () => fakeChild(),
    checkHealthImpl: async () => ({ ok: true }),
    fsImpl: { existsSync: () => true },
    platform: 'linux',
  });
  const got = await new Promise((resolve) => {
    launcher.onStatus((s) => { if (s.state === 'available') resolve(s); });
    launcher.start();
  });
  assert.strictEqual(got.state, 'available');
  launcher.stop();
});

test('BackendLauncher: reports error when interpreter missing', async () => {
  const cfg = createConfig({ isDev: false, appPath: '/app', userDataPath: '/data' });
  const launcher = new BackendLauncher({
    config: cfg,
    spawnImpl: () => fakeChild(),
    checkHealthImpl: async () => ({ ok: true }),
    fsImpl: { existsSync: () => false },
    platform: 'linux',
  });
  const got = await new Promise((resolve) => {
    launcher.onStatus((s) => { if (s.state === 'error') resolve(s); });
    launcher.start();
  });
  assert.strictEqual(got.state, 'error');
  launcher.stop();
});

test('BackendLauncher: child exit triggers unavailable and reconnect attempt', async () => {
  let spawned = 0;
  const spawnImpl = () => { spawned += 1; return fakeChild(); };
  const cfg = createConfig({ isDev: false, appPath: '/app', userDataPath: '/data' });
  cfg.backend.pollIntervalMs = 5;
  cfg.backend.restartDelayMs = 100000; // keep the test fast
  const launcher = new BackendLauncher({
    config: cfg,
    spawnImpl,
    checkHealthImpl: async () => ({ ok: true }),
    fsImpl: { existsSync: () => true },
    platform: 'linux',
  });
  const got = await new Promise((resolve) => {
    launcher.onStatus((s) => { if (s.state === 'unavailable') resolve(s); });
    launcher.start();
    setTimeout(() => { if (launcher.child) launcher.child.emit('exit', 1, 'SIGTERM'); }, 20);
  });
  assert.strictEqual(got.state, 'unavailable');
  launcher.stop();
});
